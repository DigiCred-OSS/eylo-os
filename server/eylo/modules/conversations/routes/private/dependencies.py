"""HTTP query dependencies shared by private conversation projections."""

from typing import Annotated
from uuid import UUID

from fastapi import Query

from eylo.modules.conversations.models.conversations import (
    ConversationChannels,
    ConversationStatus,
)
from eylo.modules.conversations.schemas.conversations import (
    ConversationFilterSchema,
    ConversationSort,
    ConversationSortDirection,
)


def parse_conversation_list_filters(
    conversation_ids: Annotated[
        list[UUID] | None,
        Query(alias="conversationIds", max_length=100),
    ] = None,
    agent_id: Annotated[UUID | None, Query(alias="agentId")] = None,
    query: Annotated[str | None, Query(alias="q", max_length=200)] = None,
    status: Annotated[list[ConversationStatus] | None, Query(max_length=3)] = None,
    channel: Annotated[list[ConversationChannels] | None, Query(max_length=6)] = None,
    sort: ConversationSort = ConversationSort.UPDATED_AT,
    direction: ConversationSortDirection = ConversationSortDirection.DESC,
) -> ConversationFilterSchema:
    """Expose the list read model as ordinary, shareable query parameters."""
    return ConversationFilterSchema(
        conversation_ids=conversation_ids,
        agent_id=agent_id,
        query=query,
        status=status or [],
        channel=channel or [],
        sort=sort,
        direction=direction,
    )


def require_conversation_filters(
    conversation_ids: Annotated[
        list[UUID],
        Query(alias="conversationIds", min_length=1, max_length=100),
    ],
    agent_id: Annotated[UUID | None, Query(alias="agentId")] = None,
) -> ConversationFilterSchema:
    """Parse the required conversation IDs as ordinary GET query parameters."""
    return ConversationFilterSchema(
        conversation_ids=conversation_ids,
        agent_id=agent_id,
    )


__all__ = ["parse_conversation_list_filters", "require_conversation_filters"]
