"""Agent-facing knowledge query and write system tools."""

import logging
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field

from eylo.common.contracts.knowledgebase import (
    MAX_KNOWLEDGE_QUERY_CHARS,
    MAX_KNOWLEDGE_RESULTS,
    MAX_KNOWLEDGE_SCOPE_FILTERS,
    MAX_KNOWLEDGE_TITLE_CHARS,
    KnowledgeDocument,
)
from eylo.common.database import get_transaction, start_transaction
from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.knowledgebase.access import (
    KnowledgeAccessError,
    assert_writable,
)
from eylo.modules.knowledgebase.jobs import MAX_CONTENT_BYTES
from eylo.modules.knowledgebase.services.ingestion import (
    IngestionError,
    IngestionService,
)
from eylo.modules.knowledgebase.services.knowledgebases import (
    KnowledgebaseError,
    KnowledgebaseService,
)
from eylo.pipelines.knowledgebase import query_agent_knowledge

logger = logging.getLogger(__name__)

KnowledgeQuery = Annotated[
    str,
    Field(min_length=1, max_length=MAX_KNOWLEDGE_QUERY_CHARS),
]
KnowledgeScopes = Annotated[
    list[str],
    Field(max_length=MAX_KNOWLEDGE_SCOPE_FILTERS),
]
KnowledgeWriteContent = Annotated[
    str,
    Field(min_length=1, max_length=MAX_CONTENT_BYTES),
]
KnowledgeTitle = Annotated[str, Field(min_length=1, max_length=MAX_KNOWLEDGE_TITLE_CHARS)]
KnowledgeTopK = Annotated[int, Field(ge=1, le=MAX_KNOWLEDGE_RESULTS)]


async def kb_query(
    query: KnowledgeQuery,
    scopes: KnowledgeScopes | None = None,
    top_k: KnowledgeTopK = MAX_KNOWLEDGE_RESULTS,
    ctx: ConversationContext = None,
) -> dict[str, Any]:
    """Search the knowledge available to you and return the passages that match.

    Use this whenever the answer might be recorded rather than reasoned:
    policies, product details, prior decisions, anything specific to this
    organization that you would otherwise guess at.

    Args:
        query (str): What you want to know, in natural language. Full questions
            retrieve better than single keywords.
        scopes (list[str] | None): Which knowledge to search — any of
            'organization', 'agent', 'conversation'. Omit to search everything
            available to you, which is the usual choice.
        top_k (int): Maximum passages to return, from 1 through
            8. Use fewer when one or two precise sources are enough.

    Returns:
        Dict with keys:
        - success (bool)
        - results (list): Each includes a structured citation labelled K1, K2,
          and so on, plus its typed ranking state and whether its score is
          comparable across knowledgebases. Cite those labels when using a
          passage in your answer.
        - ranking (dict): `not_requested`, `applied`, or `degraded`, with the
          pinned provider authority and a safe reason when degraded.
        - message (str): Present when there is nothing to search or nothing
          matched.

    """
    agent = getattr(ctx, "primary_agent", None) if ctx else None
    if agent is None:
        return {"success": False, "results": [], "message": "No agent in context."}
    conversation = getattr(ctx, "conversation", None)
    return await query_agent_knowledge(
        query=query,
        scopes=scopes,
        agent=agent,
        conversation_id=getattr(conversation, "id", None),
        top_k=top_k,
    )


async def kb_write_destinations(
    ctx: ConversationContext = None,
) -> dict[str, Any]:
    """List the exact knowledgebases this agent may write in this context.

    Returns only IDs, names and scopes. Call this before `kb_write`; there is no
    primary or default destination and a conversation knowledgebase is listed
    only inside its own conversation.
    """
    agent = getattr(ctx, "primary_agent", None) if ctx else None
    if agent is None:
        return {
            "success": False,
            "destinations": [],
            "message": "No agent in context.",
        }
    conversation = getattr(ctx, "conversation", None)
    conversation_id = getattr(conversation, "id", None)

    async with start_transaction(ro=True):
        grants = await KnowledgebaseService(get_transaction()).grants_for_agent(
            agent.id,
            agent.organization_id,
        )
        destinations = []
        for grant in grants:
            try:
                assert_writable(
                    [grant],
                    grant.knowledgebase_id,
                    conversation_id=conversation_id,
                )
            except KnowledgeAccessError:
                continue
            destinations.append(
                {
                    "knowledgebase_id": str(grant.knowledgebase_id),
                    "name": grant.knowledgebase.name,
                    "scope": grant.knowledgebase.scope.value,
                }
            )

    return {
        "success": True,
        "destinations": destinations,
        "message": "" if destinations else "No writable knowledgebase is available.",
    }


async def kb_write(
    content: KnowledgeWriteContent,
    knowledgebase_id: UUID,
    title: KnowledgeTitle | None = None,
    ctx: ConversationContext = None,
) -> dict[str, Any]:
    """Record something durably so it can be retrieved later.

    Use this for facts worth keeping — a decision reached, a correction the user
    made, a detail they will expect you to remember. Do not use it for
    conversational filler; everything written here comes back in future
    searches.

    Writing may be refused. Access is a property of the grant an operator made,
    not something you have by default, and a refusal is a normal outcome to
    relay rather than retry.

    Args:
        content (str): The text to record. Write it so it makes sense to
            someone reading it without this conversation.
        title (str | None): A short label for the entry.
        knowledgebase_id (UUID): Exact destination returned by
            `kb_write_destinations`. There is no default destination.

    Returns:
        Dict with keys:
        - success (bool)
        - document_id (str): Present on success.
        - message (str): On failure, why — including which knowledgebase
          refused and what access it would need.

    """
    agent = getattr(ctx, "primary_agent", None) if ctx else None
    if agent is None:
        return {"success": False, "message": "No agent in context."}
    if not content.strip():
        return {"success": False, "message": "Nothing to record."}

    conversation = getattr(ctx, "conversation", None)
    conversation_id = getattr(conversation, "id", None)

    async with start_transaction():
        session = get_transaction()
        service = KnowledgebaseService(session)
        try:
            grants = await service.grants_for_agent(
                agent.id,
                agent.organization_id,
            )
            assert_writable(
                grants,
                knowledgebase_id,
                conversation_id=conversation_id,
            )
        except (KnowledgeAccessError, KnowledgebaseError):
            return {
                "success": False,
                "message": "Knowledgebase is unavailable or not writable.",
            }

        grant = next(
            item
            for item in grants
            if str(item.knowledgebase_id) == str(knowledgebase_id)
        )
        knowledgebase = grant.knowledgebase
        document = KnowledgeDocument(
            content=content,
            title=title,
            scope=knowledgebase.scope,
            scope_id=knowledgebase.scope_id,
        )
        try:
            job = await IngestionService(session).enqueue(
                organization_id=agent.organization_id,
                knowledgebase_id=knowledgebase_id,
                document=document,
            )
        except IngestionError as error:
            return {"success": False, "message": str(error)}
        job_id = job.id
        document_id = job.document_id
        knowledgebase_name = knowledgebase.name

    from eylo.pipelines.knowledgebase.durable_execution import (
        spawn_knowledge_ingestion,
    )

    try:
        await spawn_knowledge_ingestion(
            organization_id=agent.organization_id,
            job_id=job_id,
        )
    except Exception as error:  # noqa: BLE001 - committed DB outbox is durable
        logger.error(
            "Could not immediately spawn agent knowledge write id=%s error_type=%s",
            job_id,
            type(error).__name__,
        )

    return {
        "success": True,
        "knowledgebase_id": str(knowledgebase_id),
        "job_id": str(job_id),
        "document_id": str(document_id),
        "message": f"Accepted for '{knowledgebase_name}'.",
    }
