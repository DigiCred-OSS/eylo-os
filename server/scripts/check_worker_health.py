#!/usr/bin/env python3
"""Report whether the initialized durable worker process is still alive."""

from pathlib import Path

READINESS_FILE = Path("/tmp/eylo-worker-ready")


def main() -> int:
    """Validate the readiness marker against the live worker command line."""
    try:
        worker_pid = int(READINESS_FILE.read_text(encoding="utf-8").strip())
        command_line = Path(f"/proc/{worker_pid}/cmdline").read_bytes()
    except (FileNotFoundError, PermissionError, ValueError):
        return 1
    return 0 if b"eylo.agent_run_worker" in command_line else 1


if __name__ == "__main__":
    raise SystemExit(main())
