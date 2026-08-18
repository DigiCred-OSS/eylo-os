"""Application services for the `analytics` domain."""

import datetime
from typing import Literal
from uuid import UUID

from eylo.modules.agents.models import AgentsModel
from eylo.modules.analytics.repositories import AnalyticsRepository
from eylo.modules.contacts.models import ContactsModel
from eylo.modules.conversations.models.conversations import ConversationsModel
from eylo.modules.conversations.models.messages import MessagesModel
from eylo.modules.conversations.models.participants import ParticipantsModel
from eylo.modules.members.models import MemberModel


class AnalyticsService:
    def __init__(self):
        # Initialize any required resources or connections here
        self._repository = AnalyticsRepository()

    async def _base_created_between_dates(
        self,
        table_name: str,
        organization_id: UUID,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        timeslice: Literal["day", "week", "month"] = "day",
    ) -> list:
        sql = f"""
            SELECT
                COUNT(*),
                DATE_TRUNC('{timeslice}', created_at) AS day_created
            FROM
                {table_name}
            WHERE
                organization_id = :organization_id
                AND
                created_at BETWEEN :start_date AND :end_date
            GROUP BY
                day_created
            ORDER BY
                day_created
        """
        params = {
            "organization_id": organization_id,
            "start_date": start_date,
            "end_date": end_date,
        }
        result = await self._repository.execute_query(sql, params)
        if not result:
            return []
        return [
            {
                "count": row[0],
                "date": row[1].strftime("%Y-%m-%d"),
            }
            for row in result
        ]

    async def conversations_created_between_dates(
        self,
        organization_id: UUID,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        timeslice: Literal["day", "week", "month"] = "day",
    ) -> list:
        table_name = ConversationsModel.__tablename__
        return await self._base_created_between_dates(
            table_name, organization_id, start_date, end_date, timeslice
        )

    async def members_created_between_dates(
        self,
        organization_id: UUID,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        timeslice: Literal["day", "week", "month"] = "day",
    ) -> list:
        table_name = MemberModel.__tablename__
        return await self._base_created_between_dates(
            table_name, organization_id, start_date, end_date, timeslice
        )

    async def contacts_created_between_dates(
        self,
        organization_id: UUID,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        timeslice: Literal["day", "week", "month"] = "day",
    ) -> list:
        # Assuming a similar structure for contacts as other models
        table_name = ContactsModel.__tablename__
        return await self._base_created_between_dates(
            table_name, organization_id, start_date, end_date, timeslice
        )

    async def messages_created_between_dates(
        self,
        organization_id: UUID,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        timeslice: Literal["day", "week", "month"] = "day",
    ) -> list:
        table_name = MessagesModel.__tablename__
        sql = f"""
            SELECT
                COUNT(*),
                DATE_TRUNC('{timeslice}', messages.created_at) AS day_created
            FROM
                {table_name} as messages
            INNER JOIN
                {ConversationsModel.__tablename__} AS conversations
                ON
                messages.conversation_id = conversations.id
            WHERE
                conversations.organization_id = :organization_id
                AND
                messages.created_at BETWEEN :start_date AND :end_date
            GROUP BY
                day_created
            ORDER BY
                day_created
        """
        params = {
            "organization_id": organization_id,
            "start_date": start_date,
            "end_date": end_date,
        }
        result = await self._repository.execute_query(sql, params)
        if not result:
            return []
        return [
            {
                "count": row[0],
                "date": row[1].strftime("%Y-%m-%d"),
            }
            for row in result
        ]

    async def conversations_created_per_agent(
        self,
        organization_id: UUID,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        timeslice: Literal["day", "week", "month"] = "day",
    ) -> list:
        sql = f"""
            SELECT
                agents.id AS agent_id,
                COUNT(*) AS count,
                DATE_TRUNC('{timeslice}', conversations.created_at) AS day_created
            FROM
                {ConversationsModel.__tablename__} as conversations
            INNER JOIN
                {ParticipantsModel.__tablename__} as participants ON conversations.id = participants.conversation_id
            INNER JOIN
                {AgentsModel.__tablename__} as agents ON participants.entity_id::UUID = agents.id
            WHERE
                conversations.organization_id = :organization_id
                AND
                conversations.created_at BETWEEN :start_date AND :end_date
            GROUP BY
                agents.id,
                day_created
            ORDER BY
                day_created
        """
        params = {
            "organization_id": organization_id,
            "start_date": start_date,
            "end_date": end_date,
        }
        result = await self._repository.execute_query(sql, params)
        if not result:
            return []
        return [
            {
                "agentId": str(row[0]),
                "count": row[1],
                "date": row[2].strftime("%Y-%m-%d"),
            }
            for row in result
        ]
