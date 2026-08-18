"""Private durable replay history for non-conversation AgentRuns."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from eylo.common.database import get_transaction
from eylo.framework.agents.context import RunMessage
from eylo.framework.agents.model import (
    Model,
    ModelBlockKind,
    ModelOutputBlock,
    ModelResponse,
    ModelSettings,
    ModelUsage,
)
from eylo.framework.agents.tool import ToolCall, ToolResult
from eylo.modules.agent_runs.models import (
    AgentRunModel,
    AgentRunTranscriptItemModel,
)
from eylo.pipelines.agent_run_tools import bind_agent_run_tool_command

ASSISTANT_TEXT_KIND = "assistant_text"
TOOL_CALL_KIND = "tool_call"
TOOL_RESULT_KIND = "tool_result"

_MAX_PAYLOAD_BYTES = 65_536


class AgentRunTranscriptError(ValueError):
    """Private replay history is invalid or exceeds its whole-item ceiling."""


@dataclass(frozen=True, slots=True)
class AgentRunTranscriptReplay:
    messages: tuple[RunMessage, ...]
    pending_calls: tuple[ToolCall, ...]
    command_ids: dict[str, UUID]


class AgentRunTranscript:
    """Append and replay canonical model/tool exchange for one AgentRun."""

    def __init__(self, *, organization_id: UUID, agent_run_id: UUID) -> None:
        self.organization_id = organization_id
        self.agent_run_id = agent_run_id

    async def replay(self) -> AgentRunTranscriptReplay:
        rows = list(
            (
                await get_transaction().execute(
                    select(AgentRunTranscriptItemModel)
                    .where(
                        AgentRunTranscriptItemModel.organization_id
                        == self.organization_id,
                        AgentRunTranscriptItemModel.run_id == self.agent_run_id,
                        AgentRunTranscriptItemModel.deleted.is_(False),
                    )
                    .order_by(
                        AgentRunTranscriptItemModel.sequence,
                        AgentRunTranscriptItemModel.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        resolved = {
            row.correlation_id
            for row in rows
            if row.kind == TOOL_RESULT_KIND and row.correlation_id is not None
        }
        pending_rows = [
            row
            for row in rows
            if row.kind == TOOL_CALL_KIND and row.correlation_id not in resolved
        ]
        pending_ids = {row.id for row in pending_rows}
        messages = tuple(
            _message_from_row(row) for row in rows if row.id not in pending_ids
        )
        pending_calls = tuple(
            ToolCall.model_validate(row.payload["tool_call"]) for row in pending_rows
        )
        command_ids = {
            ToolCall.model_validate(row.payload["tool_call"]).id: UUID(str(row.id))
            for row in rows
            if row.kind == TOOL_CALL_KIND
        }
        return AgentRunTranscriptReplay(
            messages=messages,
            pending_calls=pending_calls,
            command_ids=command_ids,
        )

    async def record_model_response(
        self,
        response: ModelResponse,
        tool_calls: tuple[ToolCall, ...],
    ) -> dict[str, UUID]:
        text = "\n".join(
            block.content
            for block in response.blocks
            if block.kind is ModelBlockKind.TEXT
            and isinstance(block.content, str)
            and block.content
        )
        if text:
            await self._append(
                kind=ASSISTANT_TEXT_KIND,
                correlation_id=_correlation(f"{response.id}:text"),
                payload={"text": text, "response_id": response.id},
            )

        command_ids: dict[str, UUID] = {}
        for call in tool_calls:
            row = await self._append(
                kind=TOOL_CALL_KIND,
                correlation_id=_correlation(call.id),
                payload={
                    "tool_call": call.model_dump(mode="json"),
                    "response_id": response.id,
                },
            )
            command_ids[call.id] = UUID(str(row.id))
        await get_transaction().commit()
        return command_ids

    async def record_tool_result(
        self,
        call: ToolCall,
        result: ToolResult,
    ) -> AgentRunTranscriptItemModel | None:
        if _is_pause_result(result):
            return None
        row = await self._append(
            kind=TOOL_RESULT_KIND,
            correlation_id=_correlation(call.id),
            payload={"tool_result": result.model_dump(mode="json")},
        )
        await get_transaction().commit()
        return row

    async def tool_result(self, call: ToolCall) -> ToolResult | None:
        row = await get_transaction().scalar(
            select(AgentRunTranscriptItemModel).where(
                AgentRunTranscriptItemModel.organization_id == self.organization_id,
                AgentRunTranscriptItemModel.run_id == self.agent_run_id,
                AgentRunTranscriptItemModel.kind == TOOL_RESULT_KIND,
                AgentRunTranscriptItemModel.correlation_id == _correlation(call.id),
                AgentRunTranscriptItemModel.deleted.is_(False),
            )
        )
        if row is None:
            return None
        return ToolResult.model_validate(row.payload["tool_result"])

    async def _append(
        self,
        *,
        kind: str,
        correlation_id: str | None,
        payload: dict[str, Any],
    ) -> AgentRunTranscriptItemModel:
        _require_bounded_payload(payload)
        session = get_transaction()
        existing = None
        if correlation_id is not None:
            existing = await session.scalar(
                select(AgentRunTranscriptItemModel).where(
                    AgentRunTranscriptItemModel.organization_id
                    == self.organization_id,
                    AgentRunTranscriptItemModel.run_id == self.agent_run_id,
                    AgentRunTranscriptItemModel.kind == kind,
                    AgentRunTranscriptItemModel.correlation_id == correlation_id,
                    AgentRunTranscriptItemModel.deleted.is_(False),
                )
            )
        if existing is not None:
            if existing.payload != payload:
                raise AgentRunTranscriptError(
                    "AgentRun transcript identity has different content."
                )
            return existing

        run = await session.scalar(
            select(AgentRunModel)
            .where(
                AgentRunModel.id == self.agent_run_id,
                AgentRunModel.organization_id == self.organization_id,
                AgentRunModel.deleted.is_(False),
            )
            .with_for_update()
        )
        if run is None:
            raise AgentRunTranscriptError("AgentRun transcript owner is unavailable.")
        sequence = (
            await session.scalar(
                select(func.coalesce(func.max(AgentRunTranscriptItemModel.sequence), 0))
                .where(
                    AgentRunTranscriptItemModel.organization_id
                    == self.organization_id,
                    AgentRunTranscriptItemModel.run_id == self.agent_run_id,
                    AgentRunTranscriptItemModel.deleted.is_(False),
                )
            )
            or 0
        ) + 1
        row = AgentRunTranscriptItemModel(
            organization_id=self.organization_id,
            run_id=self.agent_run_id,
            sequence=sequence,
            kind=kind,
            correlation_id=correlation_id,
            payload=payload,
        )
        session.add(row)
        await session.flush()
        return row


class AgentRunTranscriptBridge:
    """Framework callbacks that make non-conversation tool loops replayable."""

    def __init__(
        self,
        *,
        transcript: AgentRunTranscript,
        local_context: dict,
        command_ids: dict[str, UUID],
    ) -> None:
        self.transcript = transcript
        self.local_context = local_context
        self.command_ids = command_ids

    async def after_model_response(
        self,
        _context,
        _run_input,
        response: ModelResponse,
        tool_calls: tuple[ToolCall, ...],
    ) -> None:
        new_tool_calls = tuple(
            call for call in tool_calls if call.id not in self.command_ids
        )
        if not new_tool_calls:
            return
        self.command_ids.update(
            await self.transcript.record_model_response(response, new_tool_calls)
        )

    async def before_tool_call(
        self,
        _context,
        call: ToolCall,
        _response: ModelResponse,
    ) -> None:
        command_id = self.command_ids.get(call.id)
        if command_id is None:
            raise AgentRunTranscriptError(
                "Tool call has no persisted AgentRun command identity."
            )
        bind_agent_run_tool_command(
            self.local_context,
            call=call,
            command_id=command_id,
        )

    async def after_tool_result(
        self,
        _context,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
        await self.transcript.record_tool_result(call, result)


class PendingToolCallsModel:
    """Replay unresolved persisted calls once, then delegate to the real model."""

    def __init__(
        self,
        delegate: Model,
        *,
        agent_run_id: UUID,
        pending_calls: tuple[ToolCall, ...],
    ) -> None:
        self._delegate = delegate
        self._agent_run_id = agent_run_id
        self._pending_calls = pending_calls

    async def generate(
        self,
        run_input,
        settings: ModelSettings,
    ) -> ModelResponse:
        if self._pending_calls:
            calls = self._pending_calls
            self._pending_calls = ()
            return ModelResponse(
                id=f"agent-run-replay-{self._agent_run_id}",
                model=settings.model or "agent-run-replay",
                blocks=tuple(
                    ModelOutputBlock(
                        kind=ModelBlockKind.TOOL_CALL,
                        content=call.model_dump(mode="json"),
                    )
                    for call in calls
                ),
                usage=ModelUsage(),
                stop_reason="tool_use",
            )
        return await self._delegate.generate(run_input, settings)


def with_replay_messages(run_input, replay: AgentRunTranscriptReplay):
    return run_input.model_copy(
        update={"messages": (*run_input.messages, *replay.messages)}
    )


def _message_from_row(row: AgentRunTranscriptItemModel) -> RunMessage:
    if row.kind == ASSISTANT_TEXT_KIND:
        return RunMessage(
            id=row.id,
            role="assistant",
            content=str(row.payload["text"]),
            metadata={"agent_run_transcript": True},
        )
    if row.kind == TOOL_CALL_KIND:
        call = ToolCall.model_validate(row.payload["tool_call"])
        return RunMessage(
            id=row.id,
            role="assistant",
            content=f"Tool call: {call.name}",
            metadata={
                "agent_run_transcript": True,
                "tool_call": call.model_dump(mode="json"),
            },
        )
    if row.kind == TOOL_RESULT_KIND:
        result = ToolResult.model_validate(row.payload["tool_result"])
        content = (
            result.content
            if isinstance(result.content, str)
            else json.dumps(
                result.content,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return RunMessage(
            id=row.id,
            role="tool",
            content=content,
            metadata={
                "agent_run_transcript": True,
                "tool_result": result.model_dump(mode="json"),
            },
        )
    raise AgentRunTranscriptError("AgentRun transcript kind is invalid.")


def _is_pause_result(result: ToolResult) -> bool:
    return bool(
        result.metadata.get("tool_execution_paused")
        or result.metadata.get("approval_request")
        or result.metadata.get("input_request")
        or result.metadata.get("tool_execution_failed")
    )


def _correlation(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_bounded_payload(payload: dict[str, Any]) -> None:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise AgentRunTranscriptError(
            "AgentRun transcript payload is not JSON-safe."
        ) from error
    if len(encoded) > _MAX_PAYLOAD_BYTES:
        raise AgentRunTranscriptError(
            "AgentRun transcript item exceeds 65536 encoded bytes."
        )


__all__ = [
    "AgentRunTranscript",
    "AgentRunTranscriptBridge",
    "AgentRunTranscriptError",
    "AgentRunTranscriptReplay",
    "PendingToolCallsModel",
    "with_replay_messages",
]
