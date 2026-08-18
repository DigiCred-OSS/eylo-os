"""Persistence access for the `conversations` domain."""

from uuid import UUID

from sqlalchemy import and_, desc, func, select

from eylo.common.repositories import BaseORMRepository
from eylo.modules.agents.models import AgentsModel
from eylo.modules.contacts.models import ContactsModel
from eylo.modules.conversations.constants import DELETED_CONTACT_ENTITY_ID
from eylo.modules.conversations.models import ConversationsModel
from eylo.modules.conversations.models.messages import MessagesModel
from eylo.modules.conversations.models.participants import ParticipantsModel
from eylo.modules.conversations.schemas.messages import MessageKind


class ConversationAggregateRepository(BaseORMRepository[ConversationsModel]):
    """Repository for conversation aggregate queries.

    This repository handles complex JOINs to fetch conversation data
    with all related entities in a single database round-trip.
    """

    @property
    def model(self) -> type[ConversationsModel]:
        return ConversationsModel

    async def get_aggregates_by_ids(
        self,
        conversation_ids: list[UUID],
        organization_id: UUID,
        include_messages: bool = True,
        message_limit: int = 50,
        message_offset: int = 0,
        include_participants: bool = True,
        message_kinds: list[MessageKind] | None = None,
    ) -> list[dict]:
        """Fetch multiple conversations with all related data.

        This uses batch queries to minimize database round-trips:
        1. Fetch all conversations in one query
        2. Fetch all participants in one query
        3. Fetch all contacts/agents referenced by participants
        4. Fetch messages for all conversations (with limit per conversation)

        Args:
            conversation_ids: List of conversation UUIDs
            organization_id: Organization UUID
            include_messages: Whether to fetch messages
            message_limit: Max messages per conversation
            message_offset: Number of messages to skip per conversation (for pagination)
            include_participants: Whether to fetch participants

        Returns:
            List of aggregate dictionaries (same structure as get_aggregate_by_id)

        """
        if not conversation_ids:
            return []

        # 1. Fetch all conversations
        conv_query = select(ConversationsModel).where(
            and_(
                ConversationsModel.id.in_(conversation_ids),
                ConversationsModel.organization_id == organization_id,
                ConversationsModel.deleted.is_(False),
            )
        )
        conv_result = await self.db_session.execute(conv_query)
        conversations = {c.id: c for c in conv_result.scalars().all()}
        authorized_conversation_ids = list(conversations)

        # Initialize result structure
        aggregates = {
            conv_id: {
                "conversation": conversations.get(conv_id),
                "contact": None,
                "primary_agent": None,
                "all_agents": [],
                "participants": [],
                "messages": [],
                "message_count": 0,
            }
            for conv_id in authorized_conversation_ids
            if conv_id in conversations
        }

        if not aggregates:
            return []

        # 2. Fetch all participants
        if include_participants:
            participant_query = (
                select(ParticipantsModel)
                .where(
                    ParticipantsModel.conversation_id.in_(authorized_conversation_ids),
                    ParticipantsModel.deleted.is_(False),
                )
                .order_by(
                    ParticipantsModel.conversation_id, ParticipantsModel.joined_at
                )
            )
            participant_result = await self.db_session.execute(participant_query)
            all_participants = participant_result.scalars().all()

            # Group participants by conversation
            participants_by_conv = {}
            contact_ids = set()
            agent_ids = set()

            for p in all_participants:
                if p.conversation_id not in participants_by_conv:
                    participants_by_conv[p.conversation_id] = []
                participants_by_conv[p.conversation_id].append(p)

                if (
                    p.entity_kind == "CONTACT"
                    and p.entity_id != DELETED_CONTACT_ENTITY_ID
                ):
                    contact_ids.add(UUID(p.entity_id))
                elif p.entity_kind == "AGENT":
                    agent_ids.add(UUID(p.entity_id))

            # 3. Fetch all contacts
            contacts_map = {}
            if contact_ids:
                contact_query = select(ContactsModel).where(
                    and_(
                        ContactsModel.id.in_(contact_ids),
                        ContactsModel.organization_id == organization_id,
                        ContactsModel.deleted.is_(False),
                    )
                )
                contact_result = await self.db_session.execute(contact_query)
                contacts_map = {c.id: c for c in contact_result.scalars().all()}

            # 4. Fetch all agents
            agents_map = {}
            if agent_ids:
                agent_query = select(AgentsModel).where(
                    and_(
                        AgentsModel.id.in_(agent_ids),
                        AgentsModel.organization_id == organization_id,
                        AgentsModel.deleted.is_(False),
                    )
                )
                agent_result = await self.db_session.execute(agent_query)
                agents_map = {a.id: a for a in agent_result.scalars().all()}

            # 5. Populate aggregate data with participants
            for conv_id, participants in participants_by_conv.items():
                if conv_id not in aggregates:
                    continue

                conv_agents = []
                primary_agent = None
                contact = None

                for p in participants:
                    # Build participant dict
                    participant_dict = {
                        "participant": p,
                        "entity_name": None,
                    }

                    if p.entity_kind == "CONTACT":
                        if p.entity_id == DELETED_CONTACT_ENTITY_ID:
                            participant_dict["entity_name"] = DELETED_CONTACT_ENTITY_ID
                        else:
                            entity_id = UUID(p.entity_id)
                            if entity_id in contacts_map:
                                contact = contacts_map[entity_id]
                                participant_dict["entity_name"] = contact.name

                    elif p.entity_kind == "AGENT":
                        entity_id = UUID(p.entity_id)
                        if entity_id in agents_map:
                            agent = agents_map[entity_id]
                            conv_agents.append(agent)
                            participant_dict["entity_name"] = agent.name

                            # Check if this is primary agent
                            if p.is_primary:
                                primary_agent = agent

                    aggregates[conv_id]["participants"].append(participant_dict)

                # Set primary agent (fallback to most recent active)
                if not primary_agent and conv_agents:
                    active_participants = [
                        p
                        for p in participants
                        if p.entity_kind == "AGENT" and p.is_active
                    ]
                    if active_participants:
                        most_recent = max(
                            active_participants, key=lambda p: p.joined_at
                        )
                        primary_agent = agents_map.get(UUID(most_recent.entity_id))

                aggregates[conv_id]["contact"] = contact
                aggregates[conv_id]["primary_agent"] = primary_agent
                aggregates[conv_id]["all_agents"] = conv_agents

        # 6. Count messages even when callers omit message bodies.
        filters = [
            MessagesModel.conversation_id.in_(authorized_conversation_ids),
            MessagesModel.deleted.is_(False),
        ]
        if message_kinds:
            filters.append(MessagesModel.kind.in_(message_kinds))
        count_query = (
            select(
                MessagesModel.conversation_id,
                func.count(MessagesModel.id).label("count"),
            )
            .filter(*filters)
            .group_by(MessagesModel.conversation_id)
        )
        count_result = await self.db_session.execute(count_query)
        message_counts = {row.conversation_id: row.count for row in count_result}
        for conv_id in aggregates:
            aggregates[conv_id]["message_count"] = message_counts.get(conv_id, 0)

        # 7. Fetch message bodies only when requested.
        if include_messages:
            # Fetch messages with LIMIT and OFFSET per conversation using window function
            # This is a PostgreSQL-specific optimization
            message_subquery = (
                select(
                    MessagesModel,
                    func.row_number()
                    .over(
                        partition_by=MessagesModel.conversation_id,
                        order_by=(
                            desc(MessagesModel.created_at),
                            desc(MessagesModel.id),
                        ),
                    )
                    .label("rn"),
                )
                .filter(*filters)
                .subquery()
            )

            # Apply both offset and limit using row_number
            message_query = select(message_subquery).where(
                and_(
                    message_subquery.c.rn > message_offset,
                    message_subquery.c.rn <= message_offset + message_limit,
                )
            )
            message_result = await self.db_session.execute(message_query)

            # Group messages by conversation
            for row in message_result:
                conv_id = row.conversation_id
                if conv_id in aggregates:
                    aggregates[conv_id]["messages"].append(row)

            # Sort messages oldest-first for each conversation
            for conv_id in aggregates:
                aggregates[conv_id]["messages"].sort(
                    key=lambda message: (message.created_at, message.id)
                )

        return list(aggregates.values())
