"""Agent-facing sandbox tools that require a durable Agent run."""

from typing import Any

from eylo.modules.conversations.schemas.conversations import ConversationContext

# Long enough for a real program, short enough that a wedged command does not
# hold a conversation. An agent needing longer wants an objective, not a turn.
DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 300

_DURABLE_REQUIRED = (
    "Sandbox tools execute only through a durable AgentRun. Start or offload "
    "durable work before using sandbox compute."
)


async def sandbox_exec(
    command: str,
    timeout_seconds: int = DEFAULT_TIMEOUT,
    ctx: ConversationContext = None,
) -> dict[str, Any]:
    """Run a shell command in your workspace and get its output.

    The workspace is an isolated filesystem that persists between commands, so
    files you write stay until the work is finished. There is no network: if
    you need data, write it into the workspace first or ask for it through
    another tool.

    Args:
        command (str): A shell command, e.g. 'python3 analyse.py' or 'ls -la'.
        timeout_seconds (int): How long to allow, up to 300. Commands that
            exceed it are abandoned.

    Returns:
        Dict with keys:
        - success (bool): True when the command exited zero.
        - exit_code (int)
        - stdout (str), stderr (str): Returned whole or rejected whole.
        - timed_out (bool)
        - message (str): Present when there is no sandbox to run in.

    """
    del command, timeout_seconds, ctx
    return {
        "success": False,
        "error": "durable_agent_run_required",
        "exit_code": -1,
        "stdout": "",
        "stderr": "",
        "timed_out": False,
        "message": _DURABLE_REQUIRED,
    }


async def sandbox_write(
    path: str, content: str, ctx: ConversationContext = None
) -> dict[str, Any]:
    """Write a file into your workspace, creating or replacing it.

    Use this to put a program or data where a command can reach it.

    Args:
        path (str): Relative to the workspace, e.g. 'analyse.py'. Paths outside
            it are refused.
        content (str): The file's full contents.

    """
    del path, content, ctx
    return {
        "success": False,
        "error": "durable_agent_run_required",
        "message": _DURABLE_REQUIRED,
    }


async def sandbox_read(path: str, ctx: ConversationContext = None) -> dict[str, Any]:
    """Read a file from your workspace.

    Args:
        path (str): Relative to the workspace. Paths outside it are refused.

    """
    del path, ctx
    return {
        "success": False,
        "error": "durable_agent_run_required",
        "content": "",
        "message": _DURABLE_REQUIRED,
    }
