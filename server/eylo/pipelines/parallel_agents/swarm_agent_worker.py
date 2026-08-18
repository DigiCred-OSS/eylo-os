"""Run a swarm agent mini ReAct loop through pipeline composition.

Loads the target agent from DB, fetches its tools, and runs an iterative
tool-calling loop using the agent's system prompt and model. The task
instruction becomes the user message.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from eylo.common.database import start_transaction
from eylo.modules.agent_runs.budgets import meter_current_agent_run_usage
from eylo.modules.agents.services.tool_execution_utils import (
    ToolDispatchError,
    ToolInputValidationError,
    execute_exact_tool,
    resolve_model_tool,
)
from eylo.modules.conversations.schemas.messages import MessageKind
from eylo.modules.parallel_agents.schemas import TaskContent, WorkerResult
from eylo.modules.tools.schemas.indb import ToolInDb
from eylo.pipelines.llm.runtime import (
    build_llm_adapter,
    resolve_background_agent,
    response_messages,
    text_message,
    text_parts,
    tool_result_messages,
    tool_uses,
)

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5
MODEL_SAFE_TOOL_ERROR = "Error: Tool execution failed."

# Tools that workers must never call
BLOCKED_TOOL_PREFIXES = ("handoff__", "spawn_task_fnf")


class SwarmAgentWorker:
    """Runs a swarm agent's ReAct loop on a task instruction.

    Loads the agent config, builds a tool list (excluding handoff and
    spawn_task_fnf), and iterates: LLM call -> tool execution -> repeat
    until a text response is produced or MAX_ITERATIONS is reached.
    """

    def __init__(
        self,
        task_content: TaskContent,
        organization_id: UUID,
        conversation_id: UUID,
    ):
        self.task_content = task_content
        self.organization_id = organization_id
        self.conversation_id = conversation_id
        self._cached_ctx = None

    async def run(self) -> WorkerResult:
        """Execute the swarm agent's ReAct loop and return result."""
        agent, tools, resolved, system_prompt = await self._load_agent_and_tools()

        adapter = build_llm_adapter(resolved)
        request_id = uuid4()
        messages = [
            text_message(
                agent.id,
                self.conversation_id,
                MessageKind.USER,
                self.task_content.instruction,
                request_id=request_id,
            )
        ]
        last_text_parts: list[str] = []

        for iteration in range(MAX_ITERATIONS):
            response = await adapter.run_inference(
                messages=messages,
                system_prompt=system_prompt,
                tools=tools,
                llm_config=resolved.generation.to_storage(),
            )
            usage = response.usage
            await meter_current_agent_run_usage(
                input_tokens=None if usage is None else usage.input_tokens,
                output_tokens=None if usage is None else usage.output_tokens,
            )
            last_text_parts = text_parts(response.content)
            requested_tools = tool_uses(response.content)

            if not requested_tools:
                text = "\n".join(last_text_parts).strip() or "Task completed."
                return WorkerResult(
                    text=text,
                    model_used=response.model,
                    iterations_used=iteration + 1,
                )

            messages.extend(
                response_messages(
                    sender_id=agent.id,
                    conversation_id=self.conversation_id,
                    request_id=request_id,
                    response_content=response.content,
                )
            )
            results = []
            for tool_use in requested_tools:
                results.append(
                    await self._execute_tool(tool_use.name, tool_use.input, tools)
                )
            messages.extend(
                tool_result_messages(
                    sender_id=agent.id,
                    conversation_id=self.conversation_id,
                    request_id=request_id,
                    calls=requested_tools,
                    results=results,
                )
            )

            logger.debug(
                "Swarm worker iteration %d: %d tool calls",
                iteration + 1,
                len(requested_tools),
            )

        logger.warning(
            "Swarm worker hit max iterations (%d) for agent=%s",
            MAX_ITERATIONS,
            self.task_content.swarm_id,
        )
        text = (
            "\n".join(last_text_parts).strip()
            if last_text_parts
            else "Task processing reached iteration limit without a final answer."
        )
        return WorkerResult(
            text=text,
            model_used=resolved.generation.model.value,
            iterations_used=MAX_ITERATIONS,
        )

    async def _load_agent_and_tools(self):
        """Load the exact filed swarm agent revision and its exact tools."""
        async with start_transaction(ro=True):
            from eylo.modules.templates.domain import TemplateConsumerKind
            from eylo.pipelines.agents import build_executable_swarm_resolver

            if (
                self.task_content.swarm_agent_id is None
                or self.task_content.swarm_agent_revision is None
                or self.task_content.swarm_topology_id is None
                or self.task_content.swarm_topology_revision is None
            ):
                raise ValueError("Swarm task lacks exact topology/agent revisions.")
            topology = await build_executable_swarm_resolver().resolve_exact(
                organization_id=self.organization_id,
                swarm_id=self.task_content.swarm_topology_id,
                revision=self.task_content.swarm_topology_revision,
                consumer_kind=TemplateConsumerKind.SWARM_AGENT,
            )
            member = topology.member_by_agent_id(self.task_content.swarm_agent_id)
            if (
                member is None
                or member.executable_agent.ref.revision
                != self.task_content.swarm_agent_revision
            ):
                raise ValueError(
                    "Swarm task agent is not authorized by its pinned topology."
                )
            executable = member.executable_agent
            agent = executable.agent
            tools = list(executable.tools)

            # Filter out blocked tools
            tools = [
                t
                for t in tools
                if t.llm_config
                and not any(
                    t.llm_config.name.startswith(prefix)
                    for prefix in BLOCKED_TOOL_PREFIXES
                )
            ]
            resolved = await resolve_background_agent(agent)

        if not executable.system_prompt:
            raise ValueError("Swarm agent revision has no authored instructions.")
        return agent, tools, resolved, executable.system_prompt

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
        tools: list[ToolInDb],
    ) -> str | dict | list:
        """Resolve the advertised name, then dispatch by the exact stored kind."""
        # Enforce blocklist at execution time — the LLM may hallucinate
        # tool names that were filtered from its tool list
        if any(tool_name.startswith(prefix) for prefix in BLOCKED_TOOL_PREFIXES):
            logger.warning("Worker tool request rejected code=blocked_tool_prefix")
            return MODEL_SAFE_TOOL_ERROR

        try:
            tool = resolve_model_tool(tools, tool_name)
        except ToolDispatchError as error:
            logger.warning(
                "Worker tool resolution rejected error_type=%s",
                type(error).__name__,
            )
            return MODEL_SAFE_TOOL_ERROR

        try:
            ctx = await self._get_conversation_context()
            return await execute_exact_tool(tool, tool_input, ctx)
        except ToolInputValidationError:
            logger.warning(
                "Tool input rejected tool=%s@%s code=input_invalid",
                tool.id,
                tool.published_revision,
            )
            return "Error: Invalid input provided to the tool."
        except ToolDispatchError as error:
            logger.warning(
                "Worker tool dispatch rejected tool=%s@%s error_type=%s",
                tool.id,
                tool.published_revision,
                type(error).__name__,
            )
            return MODEL_SAFE_TOOL_ERROR
        except Exception as error:
            logger.warning(
                "Worker tool execution failed tool=%s@%s error_type=%s",
                tool.id,
                tool.published_revision,
                type(error).__name__,
            )
            return MODEL_SAFE_TOOL_ERROR

    async def _get_conversation_context(self):
        """Get or build a ConversationContext for tool execution (cached)."""
        if self._cached_ctx is not None:
            return self._cached_ctx

        from eylo.modules.conversations.services.conversations import (
            ConversationService,
        )
        from eylo.pipelines.conversation.context import (
            ConversationContextService,
        )

        async with start_transaction(ro=True):
            conversation = await ConversationService().get_(self.conversation_id)
            self._cached_ctx = await ConversationContextService().build(
                conversation=conversation
            )
        return self._cached_ctx
