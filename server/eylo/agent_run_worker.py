"""Process entry point for all workflows on the shared durable runtime."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from pathlib import Path

from eylo.common.database import cleanup_database
from eylo.common.models import register_models
from eylo.events.durable.workflow import register_event_delivery_workflow
from eylo.listeners.py_events import ListenerProcessRole, setup_listeners
from eylo.logging import init_logging
from eylo.modules.agent_runs.absurd import AgentRunAbsurdAdapter
from eylo.modules.agent_runs.domain import AgentRunOriginKind
from eylo.modules.agent_runs.workflow import AgentRunExecutorRouter
from eylo.periodic_work import register_periodic_workflow, seed_periodic_work
from eylo.pipelines.campaigns import (
    register_campaign_attempt_workflow,
)
from eylo.pipelines.composition import register_pipeline_extensions
from eylo.pipelines.conversation.durable_execution import (
    ConversationAgentRunExecutor,
)
from eylo.pipelines.conversation.run_failure import (
    fail_agent_run_and_converge_message,
)
from eylo.pipelines.deletions import register_deletion_workflow
from eylo.pipelines.durable_events.manifest import build_event_consumer_registry
from eylo.pipelines.knowledgebase.corpus_durable_execution import (
    register_knowledge_corpus_workflow,
)
from eylo.pipelines.knowledgebase.durable_execution import (
    register_knowledge_ingestion_workflow,
)
from eylo.pipelines.knowledgebase.reindex_durable_execution import (
    register_knowledge_reindex_workflow,
)
from eylo.pipelines.memory.durable_execution import (
    register_memory_formation_workflow,
)
from eylo.pipelines.memory.reconciliation_durable_execution import (
    register_memory_reconciliation_workflow,
)
from eylo.pipelines.memory.reindex_durable_execution import (
    register_memory_reindex_workflow,
)
from eylo.pipelines.sandbox.durable_execution import ObjectiveAgentRunExecutor
from eylo.pipelines.sandbox.sessions import discard_live_run_sessions
from eylo.pipelines.scheduler import ScheduledAgentRunExecutor
from eylo.pipelines.voice.recording_durable_execution import (
    register_voice_recording_upload_workflow,
)

logger = logging.getLogger(__name__)
_READINESS_FILE = Path("/tmp/eylo-worker-ready")


def _set_readiness(*, ready: bool) -> None:
    """Publish readiness only while this initialized worker process is alive."""
    if ready:
        _READINESS_FILE.write_text(str(os.getpid()), encoding="utf-8")
    else:
        _READINESS_FILE.unlink(missing_ok=True)


async def run_worker() -> None:
    """Register before polling and expose the exact runtime manifest in logs."""
    _set_readiness(ready=False)
    register_models()
    register_pipeline_extensions()
    setup_listeners(process_role=ListenerProcessRole.WORKER)
    adapter = AgentRunAbsurdAdapter()
    health = adapter.register_workflow(
        AgentRunExecutorRouter(
            {
                AgentRunOriginKind.MESSAGE: ConversationAgentRunExecutor(),
                AgentRunOriginKind.SCHEDULE_OCCURRENCE: ScheduledAgentRunExecutor(),
                AgentRunOriginKind.OBJECTIVE: ObjectiveAgentRunExecutor(),
            }
        ),
        compute_cleanup=discard_live_run_sessions,
        failure_handler=fail_agent_run_and_converge_message,
    )
    register_knowledge_ingestion_workflow(adapter.runtime)
    register_knowledge_corpus_workflow(adapter.runtime)
    register_knowledge_reindex_workflow(adapter.runtime)
    register_memory_formation_workflow(adapter.runtime)
    register_memory_reconciliation_workflow(adapter.runtime)
    register_memory_reindex_workflow(adapter.runtime)
    register_deletion_workflow(adapter.runtime)
    register_voice_recording_upload_workflow(adapter.runtime)
    register_campaign_attempt_workflow(adapter.runtime)
    event_registry = build_event_consumer_registry()
    register_event_delivery_workflow(adapter.runtime, event_registry)
    register_periodic_workflow(adapter.runtime)
    await seed_periodic_work(adapter.runtime)
    worker_id = f"eylo-durable:{socket.gethostname()}:{os.getpid()}"
    logger.info(
        "Durable worker registered AgentRun workflow=%s queue=%s "
        "attempts=%s timeout=%s",
        health.workflow_name,
        health.queue_name,
        health.max_attempts,
        health.has_automatic_timeout,
    )
    _set_readiness(ready=True)
    try:
        await adapter.start_worker(worker_id=worker_id)
    finally:
        _set_readiness(ready=False)
        try:
            await adapter.close()
        finally:
            await cleanup_database()


def main() -> None:
    """Run the async worker until the process receives termination."""
    init_logging()
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Durable worker stopped.")


if __name__ == "__main__":
    main()
