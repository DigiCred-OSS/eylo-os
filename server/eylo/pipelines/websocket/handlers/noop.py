"""Consume protocol no-op events without side effects."""

from eylo.modules.session_context.schemas import SessionContext
from eylo.pipelines.websocket.schemas import (
    WsRequestEvent,
)


async def handle_noop(event: WsRequestEvent, ctx: SessionContext):
    return
