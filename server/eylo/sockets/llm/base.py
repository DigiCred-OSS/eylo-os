"""LLM Vendor Base Module.

This module defines the abstract base class for all LLM vendor integrations in the Eylo platform.
It establishes a common interface for different AI providers (Anthropic, OpenAI, etc.),
allowing the system to interact with different models through a consistent API.

The module implements an adapter pattern where each vendor implements standardized
transformation methods to convert between Eylo's internal formats and vendor-specific formats.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from uuid import UUID

import arrow

from eylo.common.context_compaction import (
    latest_context_compaction,
)
from eylo.common.contracts.message_content import (
    AssistantMessageContent,
    TextContent,
    UserMessageContent,
)
from eylo.common.contracts.messages import (
    MessageContentKind,
    MessageInDb,
    MessageKind,
    RequestStatus,
)
from eylo.common.contracts.tool_record import ToolRecord
from eylo.common.utils.toon_serde import toon_encode
from eylo.sockets.llm.schemas import LLMResponse

logger = logging.getLogger(__name__)

_REQUEST_STATUSES_EXCLUDED_FROM_LLM_CONTEXT = (
    RequestStatus.INTERRUPTED,
    RequestStatus.SKIPPED,
)


class LLMVendorAdapter(ABC):
    """Abstract base class for LLM vendor adapters.

    Each vendor (Anthropic, OpenAI, Gemini, etc.) should implement
    this interface to provide vendor-specific transformations and
    API interactions.

    The adapter pattern lets platform runners use any LLM provider through a
    consistent interface, keeping vendor-specific code outside business logic.
    """

    def _handle_user_transition(
        self,
        stack: List[MessageInDb],
        msg: MessageInDb,
        current_kind: MessageKind,
        pending_tool_calls: dict[str, UUID],
    ) -> None:
        """Handle transitions from USER message state.

        Anthropic requires no consecutive same-role messages.
        If we encounter USER -> USER, we merge them.
        """
        logger.debug(
            f"[BaseAdapter] Handling USER message transition. {msg.id=} {current_kind=}"
        )
        if current_kind == MessageKind.USER:
            # Anthropic: merge consecutive USER messages
            logger.debug("Merging consecutive USER messages")
            prev_ = stack[-1]
            prev_.content = UserMessageContent(
                content=f"{prev_.content.get_text_content()}\n{msg.get_text_content()}"
            )
            # Keep the first user message, log the merge
            stack[-1] = prev_
        elif current_kind == MessageKind.ASSISTANT:
            stack.append(msg)
        else:
            logger.warning(
                f"Invalid transition: USER -> {current_kind}. Skipping message."
            )

    def _handle_assistant_transition(
        self,
        stack: List[MessageInDb],
        msg: MessageInDb,
        current_kind: MessageKind,
        pending_tool_calls: dict[str, UUID],
    ) -> None:
        """Handle transitions from ASSISTANT message state.

        From ASSISTANT, we can go to:
        - USER (new turn)
        - TOOL_USE (assistant wants to call tools)

        We reject ASSISTANT -> ASSISTANT (must merge).
        We reject TOOL_RESULT after ASSISTANT (orphaned result).
        """
        logger.debug(
            f"[BaseAdapter] Handling ASSISTANT message transition. {msg.id=} {current_kind=}"
        )
        if current_kind == MessageKind.USER:
            # Check for pending tool calls before allowing user transition
            if pending_tool_calls:
                logger.warning(
                    f"USER message after ASSISTANT with {len(pending_tool_calls.keys())} pending tool calls."
                )
                self._cleanup_incomplete_tool_sequence(stack, pending_tool_calls)
            stack.append(msg)

        elif current_kind == MessageKind.TOOL_USE:
            # Extract and validate tool_use ID
            tool_id = self._extract_tool_use_id(msg)
            if not tool_id:
                logger.error(
                    f"TOOL_USE message missing 'id' field. Rejecting message {msg.id}"
                )
                return

            # Check for duplicate tool_use ID
            if tool_id in pending_tool_calls:
                logger.error(
                    "Duplicate tool-use identity; rejecting message=%s",
                    msg.id,
                )
                return

            # Valid tool use - add to stack and track ID
            stack.append(msg)
            pending_tool_calls[tool_id] = msg.id
            logger.debug(
                "Registered tool-use message=%s pending_count=%d",
                msg.id,
                len(pending_tool_calls),
            )

        elif current_kind == MessageKind.ASSISTANT:
            # Anthropic: merge consecutive ASSISTANT messages
            logger.debug("Merging consecutive ASSISTANT messages")
            prev_ = stack[-1]
            prev_.content = AssistantMessageContent(
                content=TextContent(
                    text=f"{prev_.get_text_content()}\n{msg.get_text_content()}"
                )
            )
            stack[-1] = prev_
        elif current_kind == MessageKind.TOOL_RESULT:
            # Orphaned result - no preceding tool_use
            tool_result_id = self._extract_tool_result_id(msg)
            if tool_result_id and tool_result_id in pending_tool_calls:
                # This should not happen - tool_result after assistant when tool_use is pending
                # but we have a valid tool_use pending
                # log error and accept the message
                logger.error(
                    "Matched tool result after assistant message=%s pending_count=%d",
                    msg.id,
                    len(pending_tool_calls),
                )
                stack.append(msg)
                pending_tool_calls.pop(tool_result_id, None)
            else:
                logger.error(
                    "Orphaned tool result after assistant; rejecting message=%s "
                    "pending_count=%d",
                    msg.id,
                    len(pending_tool_calls),
                )

    def _handle_tool_use_transition(
        self,
        stack: List[MessageInDb],
        msg: MessageInDb,
        current_kind: MessageKind,
        pending_tool_calls: dict[str, UUID],
    ) -> None:
        """Handle transitions from TOOL_USE message state.

        From TOOL_USE, we can go to:
        - TOOL_RESULT (result for this or another pending tool)
        - TOOL_USE (parallel tool calls)
        - USER (user interruption - cleanup incomplete sequence)
        - ASSISTANT (assistant continues despite incomplete tools - cleanup)
        """
        logger.debug(
            f"[BaseAdapter] Handling TOOL_USE message transition. {msg.id=} {current_kind=}"
        )
        if current_kind == MessageKind.TOOL_RESULT:
            # Extract and validate tool_result ID
            tool_result_id = self._extract_tool_result_id(msg)
            if not tool_result_id:
                logger.error(
                    f"TOOL_RESULT message missing 'tool_use_id' field. Rejecting message {msg.id}"
                )
                return

            # Check if this result matches a pending tool_use
            if tool_result_id not in pending_tool_calls:
                logger.error(
                    "Orphaned tool result; rejecting message=%s pending_count=%d",
                    msg.id,
                    len(pending_tool_calls),
                )
                return

            # Valid result - add to stack and remove from pending
            stack.append(msg)
            pending_tool_calls.pop(tool_result_id, None)
            logger.debug(
                "Matched tool result message=%s remaining_count=%d",
                msg.id,
                len(pending_tool_calls),
            )

        elif current_kind == MessageKind.USER:
            # User interruption - cleanup incomplete tool sequence
            if pending_tool_calls:
                logger.warning(
                    f"USER interruption after TOOL_USE with {len(pending_tool_calls)} pending tools. "
                    "Cleaning up incomplete sequence."
                )
                self._cleanup_incomplete_tool_sequence(stack, pending_tool_calls)
            stack.append(msg)

        elif current_kind == MessageKind.ASSISTANT:
            # Assistant continues despite incomplete tools - log warning but allow
            if pending_tool_calls:
                logger.warning(
                    f"ASSISTANT after TOOL_USE with {len(pending_tool_calls)} pending "
                    "tool calls. Cleaning up incomplete sequence."
                )
                self._cleanup_incomplete_tool_sequence(stack, pending_tool_calls)
            stack.append(msg)

        elif current_kind == MessageKind.TOOL_USE:
            # Parallel tool call - extract and validate ID
            tool_id = self._extract_tool_use_id(msg)
            if not tool_id:
                logger.error(
                    f"TOOL_USE message missing 'id' field. Rejecting message {msg.id}"
                )
                return

            # Check for duplicate tool_use ID
            if tool_id in pending_tool_calls:
                logger.error(
                    "Duplicate parallel tool-use identity; rejecting message=%s",
                    msg.id,
                )
                return

            # Valid parallel tool use - add to stack and track ID
            stack.append(msg)
            pending_tool_calls[tool_id] = msg.id
            logger.debug(
                "Registered parallel tool-use message=%s pending_count=%d",
                msg.id,
                len(pending_tool_calls),
            )

    def _handle_tool_result_transition(
        self,
        stack: List[MessageInDb],
        msg: MessageInDb,
        current_kind: MessageKind,
        pending_tool_calls: dict[str, UUID],
    ) -> None:
        """Handle transitions from TOOL_RESULT message state.

        From TOOL_RESULT, we can go to:
        - ASSISTANT (all tools completed, assistant responds)
        - TOOL_RESULT (parallel tool results)
        - USER (user interruption)
        - TOOL_USE (chained tool call)
        """
        logger.debug(
            f"[BaseAdapter] Handling TOOL_RESULT message transition. {msg.id=} {current_kind=}"
        )
        if current_kind == MessageKind.ASSISTANT:
            # Accept even if pending tool calls remain (log warning)
            if pending_tool_calls:
                logger.warning(
                    f"ASSISTANT after TOOL_RESULT with {len(pending_tool_calls)} "
                    "incomplete tool calls. Accepting ASSISTANT with incomplete sequence."
                )
            stack.append(msg)

        elif current_kind == MessageKind.USER:
            # User interruption - cleanup incomplete tools
            if pending_tool_calls:
                logger.warning(
                    f"USER interruption after TOOL_RESULT with {len(pending_tool_calls)} pending tools. "
                    "Cleaning up incomplete sequence."
                )
                self._cleanup_incomplete_tool_sequence(stack, pending_tool_calls)
            stack.append(msg)

        elif current_kind == MessageKind.TOOL_USE:
            # Chained tool call - cleanup previous incomplete sequence first
            if pending_tool_calls:
                logger.warning(
                    f"TOOL_USE after TOOL_RESULT with {len(pending_tool_calls)} pending tools. "
                    "Cleaning up incomplete sequence."
                )
                self._cleanup_incomplete_tool_sequence(stack, pending_tool_calls)

            # Now handle the new tool_use
            tool_id = self._extract_tool_use_id(msg)
            if not tool_id:
                logger.error(
                    f"TOOL_USE message missing 'id' field. Rejecting message {msg.id}"
                )
                return

            if tool_id in pending_tool_calls:
                logger.error(
                    "Duplicate chained tool-use identity; rejecting message=%s",
                    msg.id,
                )
                return

            stack.append(msg)
            pending_tool_calls[tool_id] = msg.id
            logger.debug(
                "Registered chained tool-use message=%s pending_count=%d",
                msg.id,
                len(pending_tool_calls),
            )

        elif current_kind == MessageKind.TOOL_RESULT:
            # Parallel tool result - extract and validate ID
            tool_result_id = self._extract_tool_result_id(msg)
            if not tool_result_id:
                logger.error(
                    f"TOOL_RESULT message missing 'tool_use_id' field. Rejecting message {msg.id}"
                )
                return
            # Check if this result matches a pending tool_use
            if tool_result_id not in pending_tool_calls:
                logger.error(
                    "Orphaned parallel tool result; rejecting message=%s "
                    "pending_count=%d",
                    msg.id,
                    len(pending_tool_calls),
                )
                return

            # Valid parallel result - add to stack and remove from pending
            stack.append(msg)
            pending_tool_calls.pop(tool_result_id, None)
            logger.debug(
                "Matched parallel tool result message=%s remaining_count=%d",
                msg.id,
                len(pending_tool_calls),
            )

    def _extract_tool_use_id(self, msg: MessageInDb) -> Optional[str]:
        """Extract tool_use ID from TOOL_USE message.

        Args:
            msg: Message with kind=TOOL_USE

        Returns:
            Tool use ID if found, None otherwise

        """
        try:
            if not msg.content:
                return None

            # Handle ToolUseMessageContent schema
            if hasattr(msg.content, "content") and hasattr(msg.content.content, "id"):
                return msg.content.content.id

            # Handle dict format: {"role": "tool_use", "content": {"id": "...", ...}}
            if isinstance(msg.content, dict):
                content = msg.content.get("content", {})
                if isinstance(content, dict):
                    return content.get("id")

            return None
        except Exception as error:
            logger.error(
                "Tool-use identity extraction failed message=%s error_type=%s",
                msg.id,
                type(error).__name__,
            )
            return None

    def _extract_tool_result_id(self, msg: MessageInDb) -> Optional[str]:
        """Extract tool_call_id from TOOL_RESULT message.

        Args:
            msg: Message with kind=TOOL_RESULT

        Returns:
            Tool call ID if found, None otherwise

        """
        try:
            if not msg.content:
                return None

            # Handle ToolResultMessageContent schema
            if hasattr(msg.content, "content") and isinstance(
                msg.content.content, list
            ):
                if len(msg.content.content) > 0:
                    result = msg.content.content[0]
                    if hasattr(result, "tool_use_id"):
                        return result.tool_use_id

            # Handle dict format: {"role": "user", "content": [{"tool_use_id": "...", ...}]}
            if isinstance(msg.content, dict):
                content = msg.content.get("content", [])
                if isinstance(content, list) and len(content) > 0:
                    result = content[0]
                    if isinstance(result, dict):
                        return result.get("tool_use_id")

            return None
        except Exception as error:
            logger.error(
                "Tool-result identity extraction failed message=%s error_type=%s",
                msg.id,
                type(error).__name__,
            )
            return None

    def _cleanup_incomplete_tool_sequence(
        self, stack: List[MessageInDb], pending_tool_calls: dict[str, UUID]
    ) -> None:
        """Remove incomplete tool sequences from stack.

        Removes all TOOL_USE and TOOL_RESULT messages from the end of the stack
        until we reach an ASSISTANT or USER message.

        Args:
            stack: Message stack to clean
            pending_tool_calls: Set of pending tool call IDs (will be cleared)

        """
        if not stack:
            return

        for msg in reversed(stack):
            if msg.kind in (MessageKind.TOOL_USE, MessageKind.TOOL_RESULT):
                for tool_id, msg_id in list(pending_tool_calls.items()):
                    if msg.id == msg_id:
                        logger.warning(
                            "Removed incomplete %s message=%s from sequence",
                            msg.kind.value,
                            msg.id,
                        )
                        stack.remove(msg)
                        pending_tool_calls.pop(tool_id)

    def _validate_tool_call_completeness(
        self, messages: List[MessageInDb]
    ) -> Dict[str, Any]:
        """Generate validation report for tool call completeness.

        Args:
            messages: List of messages to validate

        Returns:
            Dictionary containing:
            - total_tool_uses: Count of TOOL_USE messages
            - total_tool_results: Count of TOOL_RESULT messages
            - matched_pairs: Count of successfully matched pairs
            - missing_results: List of tool_use IDs without results
            - orphaned_results: List of tool_result IDs without matching tool_use
            - is_complete: Boolean indicating all tools are matched

        """
        tool_uses: Dict[str, MessageInDb] = {}
        tool_results: Dict[str, MessageInDb] = {}

        # Collect all tool uses and results
        for msg in messages:
            if msg.kind == MessageKind.TOOL_USE:
                tool_id = self._extract_tool_use_id(msg)
                if tool_id:
                    tool_uses[tool_id] = msg

            elif msg.kind == MessageKind.TOOL_RESULT:
                tool_id = self._extract_tool_result_id(msg)
                if tool_id:
                    tool_results[tool_id] = msg

        # Find matched, missing, and orphaned
        matched = set(tool_uses.keys()) & set(tool_results.keys())
        missing_results = set(tool_uses.keys()) - set(tool_results.keys())
        orphaned_results = set(tool_results.keys()) - set(tool_uses.keys())

        report = {
            "total_tool_uses": len(tool_uses),
            "total_tool_results": len(tool_results),
            "matched_pairs": len(matched),
            "missing_results": list(missing_results),
            "orphaned_results": list(orphaned_results),
            "is_complete": len(missing_results) == 0 and len(orphaned_results) == 0,
        }

        if not report["is_complete"]:
            logger.debug(
                "Tool-call validation incomplete uses=%d results=%d matched=%d "
                "missing=%d orphaned=%d",
                report["total_tool_uses"],
                report["total_tool_results"],
                report["matched_pairs"],
                len(missing_results),
                len(orphaned_results),
            )

        return report

    def _process_message_transition(
        self, group_messages: List[MessageInDb]
    ) -> List[MessageInDb]:
        """Process message transition based on current stack state.

        This method implements a state machine that validates message transitions
        and tracks tool call completeness. It supports parallel tool calls where
        multiple TOOL_USE messages can be followed by multiple TOOL_RESULT messages.

        Args:
            group_messages: Messages in a single request group

        Returns:
            Validated and cleaned message stack

        """
        stack: List[MessageInDb] = []
        pending_tool_calls: dict[str, UUID] = {}

        for msg in group_messages:
            current_kind = msg.kind
            # Skip SYSTEM messages (handled separately as system prompt)
            if current_kind == MessageKind.SYSTEM:
                continue

            # First message must be USER
            if not stack:
                if current_kind == MessageKind.USER:
                    stack.append(msg)
                else:
                    logger.warning(
                        f"Skipping first message with invalid kind: {current_kind}. "
                        "First message must be USER."
                    )
                continue

            # Process transitions based on current state
            last_kind = stack[-1].kind
            # [anthropic] user -> assistant -> tool-use -> tool-result -> assistant
            # [anthropic] user -> assistant
            # [openai] user -> tool-use -> tool-result

            if last_kind == MessageKind.USER:
                self._handle_user_transition(
                    stack, msg, current_kind, pending_tool_calls
                )
            elif last_kind == MessageKind.ASSISTANT:
                self._handle_assistant_transition(
                    stack, msg, current_kind, pending_tool_calls
                )
            elif last_kind == MessageKind.TOOL_USE:
                self._handle_tool_use_transition(
                    stack, msg, current_kind, pending_tool_calls
                )
            elif last_kind == MessageKind.TOOL_RESULT:
                self._handle_tool_result_transition(
                    stack, msg, current_kind, pending_tool_calls
                )

        # Remove incomplete tool sequences at the end
        self._cleanup_incomplete_tool_sequence(stack, pending_tool_calls)

        return stack

    def _enrich_user_messages_with_timestamps(
        self, messages: List[MessageInDb]
    ) -> List[MessageInDb]:
        """Enrich user messages with timestamps in content.

        Args:
            messages: List of messages to enrich

        Returns:
            List of messages with enriched user messages

        """
        enriched_messages: List[MessageInDb] = []
        for msg in messages:
            if msg.kind == MessageKind.USER:
                timestamp = msg.created_at.isoformat()
                enriched_msg = MessageInDb(
                    **msg.model_dump(exclude={"content"}),
                    content=self._append_text_to_user_content(
                        msg,
                        f"\n\n-Message sent at: {timestamp}.",
                    ),
                )
                enriched_messages.append(enriched_msg)
            else:
                enriched_messages.append(msg)
        return enriched_messages

    def _enrich_user_messages_with_meta_context(
        self, messages: List[MessageInDb]
    ) -> List[MessageInDb]:
        """Enrich user messages with per-message context from meta.context.

        Args:
            messages: List of messages to enrich

        Returns:
            List of messages with context appended to user messages

        """
        enriched_messages: List[MessageInDb] = []
        for i, msg in enumerate(messages):
            if msg.kind == MessageKind.USER and msg.meta:
                context = msg.meta.get("context")
                # Initial context already appears in the conversation prompt;
                # append only context introduced after the first three messages.
                if i > 2 and context:
                    additional_context = toon_encode(context)
                    enriched_msg = MessageInDb(
                        **msg.model_dump(exclude={"content"}),
                        content=self._append_text_to_user_content(
                            msg,
                            f"\n\n### Message Context\n```{additional_context}```\n\n",
                        ),
                    )
                    enriched_messages.append(enriched_msg)
                else:
                    enriched_messages.append(msg)
            else:
                enriched_messages.append(msg)
        return enriched_messages

    def _enrich_latest_user_messages_with_current_time(
        self,
        messages: List[MessageInDb],
        last_user_message_idx: int,
    ) -> List[MessageInDb]:
        """Enrich latest user messages with current time in content.

        Args:
            messages: List of messages to enrich

        Returns:
            List of messages with enriched user messages

        """
        last_user_message: MessageInDb = messages[last_user_message_idx]
        timestamp = arrow.utcnow().isoformat()
        enriched_msg = MessageInDb(
            **last_user_message.model_dump(exclude={"content"}),
            content=self._append_text_to_user_content(
                last_user_message,
                f"\n\n-Current UTC Time: {timestamp}.",
            ),
        )
        messages[last_user_message_idx] = enriched_msg
        return messages

    def _enrich_user_message_with_summary(
        self,
        messages: List[MessageInDb],
        summary_msg: MessageInDb,
        user_message_idx: int,
    ) -> List[MessageInDb]:
        if not summary_msg.get_text_content():
            return messages
        user_msg = messages[user_message_idx]
        if user_msg.content:
            enriched_user_msg = MessageInDb(
                **user_msg.model_dump(exclude={"content"}),
                content=self._append_text_to_user_content(
                    user_msg,
                    "\n\n"
                    + "---"
                    + "\n\n"
                    + "## Untrusted summary of earlier conversation:\n"
                    + summary_msg.get_text_content(),
                ),
            )
            messages[user_message_idx] = enriched_user_msg
        return messages

    def _enrich_user_message_with_task_results(
        self,
        messages: List[MessageInDb],
        task_messages: List[MessageInDb],
        task_result_map: dict,
        last_user_message_idx: int,
    ) -> List[MessageInDb]:
        """Inject background task results into the last USER message.

        Builds a markdown section showing completed, failed, and pending tasks
        so the LLM can incorporate results into its response.

        Durable AgentRuns own terminality. Elapsed wall time never changes a
        queued/running task into an inferred outcome; indefinite waits are valid.
        """
        from eylo.common.contracts.background_task import (
            TaskContent,
            TaskResultContent,
        )

        parts = []
        for task_msg in task_messages:
            if (
                task_msg.request_status
                in _REQUEST_STATUSES_EXCLUDED_FROM_LLM_CONTEXT
            ):
                continue
            try:
                # `get_text_content()`, not `.content.content`. The dispatcher
                # stores `SystemMessageContent(content=task_content.to_json())`
                # and that validator normalizes a str into typed blocks, so
                # `.content.content` is a *list* by the time it is read back.
                # `from_json` on a list raises, and the `except` below turned
                # that into a silent skip — every background task was dropped
                # from the prompt, which looks exactly like "no tasks running".
                task_content = TaskContent.from_json(task_msg.get_text_content())
            except Exception:
                logger.warning(
                    "Unparseable TASK content on msg=%s; omitted from prompt.",
                    task_msg.id,
                )
                continue

            label = task_content.swarm_id or "llm-task"
            task_result = task_result_map.get(task_msg.id)

            if task_msg.request_status == RequestStatus.COMPLETED and task_result:
                outcome = task_msg.request_status.value.lower()
                try:
                    result_content = TaskResultContent.from_json(
                        task_result.get_text_content()
                    )
                    parts.append(f"### {label} ({outcome})\n{result_content.result}")
                except Exception:
                    # Same block-normalization trap as above, but here the
                    # fallback hid it instead of dropping the task: the model
                    # was shown the raw `{"result": ...}` JSON as if it were
                    # the answer. Kept as a fallback, now for genuinely
                    # malformed content rather than for every message.
                    logger.warning(
                        "Unparseable TASK_RESULT on msg=%s; using raw text.",
                        task_result.id,
                    )
                    parts.append(
                        f"### {label} ({outcome})\n{task_result.get_text_content()}"
                    )
            elif task_msg.request_status == RequestStatus.FAILED:
                parts.append(f"### {label} (failed)\nTask failed.")
            else:
                if task_msg.request_status == RequestStatus.PENDING:
                    parts.append(
                        f"### {label} (queued)\n"
                        f"Not started yet: {task_content.instruction[:100]}..."
                    )
                else:
                    parts.append(
                        f"### {label} (in progress)\n"
                        f"Task is still running: {task_content.instruction[:100]}..."
                    )

        if not parts:
            return messages

        injection = "## Background Task Results\n\n" + "\n\n".join(parts)

        user_msg = messages[last_user_message_idx]

        enriched_user_msg = MessageInDb(
            **user_msg.model_dump(exclude={"content"}),
            content=self._append_text_to_user_content(
                user_msg,
                "\n\n---\n\n" + injection,
            ),
        )
        messages[last_user_message_idx] = enriched_user_msg

        logger.debug("Injected %d task results into last user message", len(parts))
        return messages

    @staticmethod
    def _append_text_to_user_content(
        message: MessageInDb,
        suffix: str,
    ) -> UserMessageContent:
        """Append text context while preserving non-text content blocks."""
        if message.content_kind != MessageContentKind.TEXT:
            return UserMessageContent(
                content=TextContent(text=(message.get_text_content() or "") + suffix)
            )

        parsed = UserMessageContent.model_validate(message.content)
        blocks = list(parsed.content)
        for index in range(len(blocks) - 1, -1, -1):
            block = blocks[index]
            if isinstance(block, TextContent):
                blocks[index] = TextContent(text=block.text + suffix)
                return UserMessageContent(content=blocks)

        return UserMessageContent(content=[*blocks, TextContent(text=suffix)])

    def _validate_message_sequence(
        self, messages: List[MessageInDb]
    ) -> List[MessageInDb]:
        """Validate and clean message sequence for vendor compatibility.

        Base implementation provides common validation logic.
        Vendors should override this to add vendor-specific rules.

        Common validations:
        - Removes messages with missing required fields
        - Ensures messages are chronologically sorted
        - Basic sanity checks

        Args:
            messages: Platform-native message objects

        Returns:
            Validated and potentially filtered list of messages

        """
        if not messages:
            return []

        # A validated persisted summary replaces the exact message range through
        # its cursor. Invalid summary metadata fails open to full history.
        compaction = latest_context_compaction(messages)
        compacted_through = (
            None
            if compaction is None
            else (compaction.boundary.created_at, str(compaction.boundary.id))
        )
        task_messages = []
        task_result_map = {}  # parent_message_id -> TASK_RESULT message
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if msg.kind == MessageKind.SYSTEM:
                if msg.content_kind == MessageContentKind.TASK and (
                    compacted_through is None
                    or (msg.created_at, str(msg.id)) > compacted_through
                ):
                    task_messages.append(msg)
                if (
                    msg.content_kind == MessageContentKind.TASK_RESULT
                    and msg.parent_message_id
                    and msg.parent_message_id not in task_result_map
                    and (
                        compacted_through is None
                        or (msg.created_at, str(msg.id)) > compacted_through
                    )
                ):
                    task_result_map[msg.parent_message_id] = msg

        # Basic validation: filter messages with missing required fields
        validated: List[MessageInDb] = []
        for msg in messages:
            if not msg.content or not msg.sender_participant_id:
                logger.warning(f"Skipping message {msg.id} - missing required fields")
                continue
            try:
                msg.get_parsed_content()
            except ValueError as exc:
                logger.warning(
                    "Skipping message %s - malformed %s content error_type=%s",
                    msg.id,
                    msg.kind,
                    type(exc).__name__,
                )
                continue
            validated.append(msg)

        # SYSTEM summaries were captured above for later
        # injection.  Remove them before request grouping — they have
        # request_id=None which is incompatible with group_by_request_id().
        validated = [
            message
            for message in validated
            if message.kind != MessageKind.SYSTEM
            and (
                compacted_through is None
                or (message.created_at, str(message.id)) > compacted_through
            )
        ]

        # INTERRUPTED and SKIPPED describe the request as a whole, not one
        # individual row. Discard the complete request group so a partial or
        # mixed-status group cannot leak stale work back into a later
        # model prompt. COMPLETED and FAILED requests remain useful history.
        excluded_request_ids = {
            message.request_id
            for message in validated
            if message.request_id is not None
            and message.request_status
            in _REQUEST_STATUSES_EXCLUDED_FROM_LLM_CONTEXT
        }
        if excluded_request_ids:
            logger.debug(
                "Excluding %d interrupted or skipped request groups from LLM context",
                len(excluded_request_ids),
            )
            validated = [
                message
                for message in validated
                if message.request_id not in excluded_request_ids
            ]

        # Ensure chronological order
        validated.sort(key=lambda m: (m.created_at, str(m.id)))
        logger.debug(f"Base validation: {len(messages)} -> {len(validated)} messages")

        request_groups = self.group_by_request_id(validated)
        sorted_requests = self.sort_request_groups(validated)
        valid_message_group = []
        pending_groups = []
        for request_id in sorted_requests:
            messages_in_group = request_groups.get(request_id, [])
            # because of this
            # there could be a case
            # where use is chatting with assistant
            # and some background job (the scheduler agent)
            # adds a new <user message> to the conversation
            # in such cases there could be two user messages in non-terminal state
            # TODO
            has_user_request_completed = any(
                m.request_status in [RequestStatus.COMPLETED, RequestStatus.FAILED]
                and m.kind == MessageKind.USER
                for m in messages_in_group
            )
            # if any messages are completed/failed, only use those

            if has_user_request_completed:
                valid_messages = self._process_message_transition(messages_in_group)
                logger.debug(
                    f"Request {request_id}: "
                    f"Original messages={len(messages_in_group)}, "
                    f"Valid messages={len(valid_messages)} ,"
                )
                valid_message_group.extend(valid_messages)
            else:
                pending_groups.append(messages_in_group)

        # push the incomplete user requests to the end
        if len(pending_groups) > 1:
            # only one pending group allowed
            for group in pending_groups[:-1]:
                valid_messages = self._process_message_transition(group)
                valid_message_group.extend(valid_messages)
        # now all the messages should be validated once
        # to make sure the complete sequences are valid
        valid_message_group = self._process_message_transition(valid_message_group)
        if pending_groups:
            # append the last pending group
            # because it is the most recent one
            # forget older pending groups
            valid_message_group.extend(pending_groups[-1])

        last_user_message_idx = None
        for i in range(len(valid_message_group) - 1, -1, -1):
            if valid_message_group[i].kind == MessageKind.USER:
                last_user_message_idx = i
                break
        first_user_message_idx = next(
            (
                i
                for i, message in enumerate(valid_message_group)
                if message.kind == MessageKind.USER
            ),
            None,
        )
        messages = self._enrich_user_messages_with_timestamps(valid_message_group)
        messages = self._enrich_user_messages_with_meta_context(messages)
        if last_user_message_idx is None:
            return messages
        messages = self._enrich_latest_user_messages_with_current_time(
            messages, last_user_message_idx
        )

        # Inject background task results into last USER message.
        if task_messages and last_user_message_idx is not None:
            messages = self._enrich_user_message_with_task_results(
                messages, task_messages, task_result_map, last_user_message_idx
            )

        if compaction is None or first_user_message_idx is None:
            return messages
        return self._enrich_user_message_with_summary(
            messages, compaction.summary, first_user_message_idx
        )

    @abstractmethod
    def get_client(self) -> Any:
        """Get a configured vendor-specific client."""
        pass

    @abstractmethod
    def transform_messages_to_vendor(
        self, messages: List[MessageInDb], system_prompt: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Transform Eylo's generic messages to a vendor-specific format."""
        pass

    @abstractmethod
    def transform_tools_to_vendor(
        self, tools: List["ToolRecord"]
    ) -> List[Dict[str, Any]]:
        """Transform Eylo's platform-native tools to a vendor-specific format."""
        pass

    @abstractmethod
    def transform_response_to_platform(self, vendor_response: Any) -> "LLMResponse":
        """Transform vendor-specific response to platform-native LLMResponse.

        This method must be implemented by all adapters to convert their
        vendor's response format into the standardized LLMResponse format.

        Args:
            vendor_response: The raw response from the vendor's API

        Returns:
            LLMResponse: Standardized platform response

        """
        pass

    @abstractmethod
    def run_inference(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
        stream: bool = False,
    ) -> Any:
        """Run inference against the vendor's API."""
        pass

    async def run_streaming_inference(
        self,
        messages: List[MessageInDb],
        system_prompt: str,
        tools: List[ToolRecord],
        llm_config: Dict[str, Any],
    ) -> AsyncIterator[LLMResponse]:
        """Run streaming inference against the vendor's API (optional)."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support streaming inference"
        )

    def group_by_request_id(
        self, messages: List[MessageInDb]
    ) -> Dict[UUID, List[MessageInDb]]:
        """Group messages by their request_id."""
        from eylo.common.utils.messages import group_messages_by_request_id

        return group_messages_by_request_id(messages)

    def sort_request_groups(self, messages: List[MessageInDb]) -> List[UUID]:
        """Sort request IDs based on the chronological order of user messages."""
        from eylo.common.utils.messages import sort_request_groups_by_user_message

        return sort_request_groups_by_user_message(messages)
