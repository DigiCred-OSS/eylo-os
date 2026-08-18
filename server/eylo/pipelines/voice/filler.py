"""Filler phrase injection for voice pipeline latency masking.

Sends short filler phrases to TTS during LLM "thinking" gaps to avoid
dead silence. Fillers are automatically interrupted when real LLM tokens arrive
via the TTS manager's turn_id mechanism.

Configuration is read from ``session_state.filler_config`` (a dict matching
:class:`~eylo.modules.voice.schemas.api.FillerConfig`).  When no config is
present the built-in defaults are used.

Usage:
    - schedule_filler() when an awaited LLM inference starts
    - cancel_filler() before the first ordered response segment or at turn end
"""

import asyncio
import logging
import random
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Built-in defaults used when no per-agent config is present.
_DEFAULT_PHRASES = [
    "Let me look into that.",
    "One moment.",
    "Let me check.",
    "Just a moment.",
    "Let me think about that.",
    "Give me a second.",
]
_DEFAULT_DELAY_S = 0.6


class FillerPhraseManager:
    """Manages delayed filler phrase injection per conversation.

    Thread-safe via asyncio — all methods must be called from the same event loop.
    """

    _pending: dict[UUID, asyncio.Task] = {}

    @classmethod
    async def schedule_filler(
        cls,
        conversation_id: UUID,
        organization_id: UUID,
    ) -> None:
        """Schedule a filler phrase using config looked up from the active session.

        If a filler is already pending for this conversation it is cancelled
        before scheduling a new one.
        """
        cls.cancel_filler(conversation_id)
        task = asyncio.create_task(cls._inject_filler(conversation_id, organization_id))
        cls._pending[conversation_id] = task

    @classmethod
    def cancel_filler(cls, conversation_id: UUID) -> None:
        """Cancel any pending filler for *conversation_id*."""
        task = cls._pending.pop(conversation_id, None)
        if task and not task.done():
            task.cancel()
            logger.debug(
                "Cancelled pending filler for conversation %s", conversation_id
            )

    @classmethod
    async def _inject_filler(
        cls,
        conversation_id: UUID,
        organization_id: UUID,
        *,
        ws_manager=None,
    ) -> None:
        """Wait, then push a filler phrase through the TTS pipeline.

        The filler uses its own turn_id so the real LLM response (which
        carries a different turn_id) will trigger the TTS manager's
        automatic interrupt logic.
        """
        # Late import to avoid circular dependency at module load time.
        if ws_manager is None:
            from eylo.pipelines.websocket.singleton import S_ws_manager

            ws_manager = S_ws_manager

        # Read filler config from the first matching voice session.
        config = await cls._get_filler_config(
            ws_manager, conversation_id, organization_id
        )
        enabled = config.get("enabled", True)
        if not enabled:
            cls._pending.pop(conversation_id, None)
            return

        phrases = config.get("phrases") or _DEFAULT_PHRASES
        delay_s = (config.get("delay_ms") or (_DEFAULT_DELAY_S * 1000)) / 1000.0

        try:
            await asyncio.sleep(delay_s)
        except asyncio.CancelledError:
            return

        if not await cls._agent_is_thinking(
            ws_manager, conversation_id, organization_id
        ):
            logger.debug(
                "Skipping filler for conversation %s: agent is no longer thinking",
                conversation_id,
            )
            cls._pending.pop(conversation_id, None)
            return

        # Guard: if TTS is already producing audio for this conversation,
        # don't inject a filler — it would abruptly cut the current audio.
        if await cls._tts_is_active(ws_manager, conversation_id, organization_id):
            logger.debug(
                "Skipping filler for conversation %s: TTS already active",
                conversation_id,
            )
            cls._pending.pop(conversation_id, None)
            return

        filler_turn_id = f"filler-{uuid4()}"
        request_id = uuid4()
        filler_text = random.choice(phrases)

        logger.info(
            "Injecting filler for conversation %s (turn=%s chars=%d)",
            conversation_id,
            filler_turn_id,
            len(filler_text),
        )

        try:
            await ws_manager.conversation_tts_to_session(
                conversation_id=conversation_id,
                organization_id=organization_id,
                payload={
                    "type": "text",
                    "text": filler_text,
                    "turn_id": filler_turn_id,
                    "request_id": str(request_id),
                    "policy_source": "filler",
                },
            )
            await ws_manager.conversation_tts_to_session(
                conversation_id=conversation_id,
                organization_id=organization_id,
                payload={
                    "type": "finalize",
                    "turn_id": filler_turn_id,
                    "request_id": str(request_id),
                    "policy_source": "filler",
                },
            )
        except Exception as error:
            logger.error(
                "Failed to inject filler conversation=%s error_type=%s",
                conversation_id,
                type(error).__name__,
            )
        finally:
            cls._pending.pop(conversation_id, None)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    async def _get_filler_config(
        cls,
        ws_manager,
        conversation_id: UUID,
        organization_id: UUID,
    ) -> dict:
        """Return the filler config dict from the first voice session, or empty dict."""
        session_ids = await ws_manager.get_sessions_for_conversation(
            organization_id, conversation_id
        )
        for session_id in session_ids:
            session_state = ws_manager.get_session_state(
                organization_id, str(session_id)
            )
            if session_state and session_state.filler_config:
                return session_state.filler_config
        return {}

    @classmethod
    async def _agent_is_thinking(
        cls,
        ws_manager,
        conversation_id: UUID,
        organization_id: UUID,
    ) -> bool:
        """Return True while the LLM is still preparing the agent response."""
        session_ids = await ws_manager.get_sessions_for_conversation(
            organization_id, conversation_id
        )
        for session_id in session_ids:
            session_state = ws_manager.get_session_state(
                organization_id, str(session_id)
            )
            if session_state and getattr(session_state, "is_agent_thinking", False):
                return True
        return False

    @classmethod
    async def _tts_is_active(
        cls,
        ws_manager,
        conversation_id: UUID,
        organization_id: UUID,
    ) -> bool:
        """Return True if any session for *conversation_id* has active TTS."""
        session_ids = await ws_manager.get_sessions_for_conversation(
            organization_id, conversation_id
        )
        for session_id in session_ids:
            session_state = ws_manager.get_session_state(
                organization_id, str(session_id)
            )
            if not session_state:
                continue
            tts = session_state.tts_manager or session_state.tts_socket
            if tts:
                is_playback_active = getattr(tts, "is_playback_active", None)
                if callable(is_playback_active):
                    if bool(is_playback_active()):
                        return True
                elif getattr(tts, "_active_turn_id", None) is not None:
                    return True
            # Also check the consumer queue for buffered audio
            q = session_state.tts_response_queue
            if q and not q.empty():
                return True
        return False
