"""Pipeline-backed fire-and-forget parallel task dispatch system tool.

Creates a SYSTEM/TASK message and its durable AgentRun. Returns
immediately — the worker runs independently in the background.
"""

from __future__ import annotations

from typing import Optional

from eylo.modules.conversations.schemas.conversations import ConversationContext
from eylo.modules.conversations.schemas.messages import MessageKind
from eylo.modules.parallel_agents.schemas import SpawnTaskFnfInput, SpawnTaskFnfResult
from eylo.pipelines.parallel_agents.task_dispatcher import TaskDispatcher


async def spawn_task_fnf(
    instruction: str,
    swarm_id: Optional[str] = None,
    *,
    ctx: ConversationContext,
) -> str:
    """Dispatch a background task to a swarm agent or bare LLM.

    The task runs independently — results are available on the next turn.
    Include ALL context the worker needs in the instruction, as it has
    no access to conversation history.

    Args:
        instruction: Self-contained task description (max 4000 chars).
        swarm_id: Slug of the swarm agent to route to, or None for a
            bare LLM call with no tools.
        ctx: Conversation context (injected by agent executor).

    Returns:
        JSON string with task_id, status, and instruction echo.

    """
    # Get request_id from the latest user message
    latest_user_message = next(
        (
            message
            for message in reversed(ctx.messages or [])
            if message.kind == MessageKind.USER
        ),
        None,
    )
    request_id = latest_user_message.request_id if latest_user_message else None

    dispatcher = TaskDispatcher(ctx)
    result: SpawnTaskFnfResult = await dispatcher.dispatch(
        instruction=instruction,
        swarm_id=swarm_id,
        request_id=request_id,
    )

    return result.model_dump_json()


spawn_task_fnf.__eylo_schema_model__ = SpawnTaskFnfInput
spawn_task_fnf.__eylo_feature_flag__ = "ENABLE_SPAWN_TASK_FNF"
