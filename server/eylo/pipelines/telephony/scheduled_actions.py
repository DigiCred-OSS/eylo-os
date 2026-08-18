"""Pipeline-backed telephony capabilities a schedule can invoke.

The scheduler supplies the stable run ID. The call pipeline uses it as the
DB-first call identity, so an at-least-once worker replay observes the same
outbound ledger entry and never creates a second paid call.
"""

from __future__ import annotations

import logging
from uuid import UUID

from eylo.modules.scheduler.actions import ActionContext, schedulable

logger = logging.getLogger(__name__)


@schedulable(
    "telephony.place_call",
    # Operator-and-campaign only. An agent that could schedule outbound calls
    # could be talked into scheduling them, and this one spends money and rings
    # a real person — `schedule_call` remains the agent's route, and it goes
    # through the same handler with the same checks.
    agent_schedulable=False,
)
async def place_call(payload: dict, *, context: ActionContext) -> dict:
    """Initiate one outbound call.

    The run row owns execution recovery; the outbound ledger owns the charged
    effect boundary.
    """
    from eylo.pipelines.telephony.call_control import VoiceService

    to_number = str(payload.get("to_number") or "").strip()
    agent_id = context.agent_id
    agent_revision = context.agent_revision

    if not to_number:
        # Terminal by nature — a payload missing this will miss it every time.
        raise ValueError("telephony.place_call requires a to_number.")
    if agent_id is None or agent_revision is None:
        raise ValueError(
            "telephony.place_call requires the run's exact agent reference."
        )

    result = await VoiceService().initiate_outbound_call(
        call_id=context.run_id,
        to_number=to_number,
        agent_id=UUID(str(agent_id)),
        agent_revision=agent_revision,
        organization_id=context.organization_id,
        initial_message=payload.get("initial_message"),
        context={
            **payload,
            "schedule_id": str(context.schedule_id),
            "schedule_revision": context.schedule_revision,
            "schedule_run_id": str(context.run_id),
        },
    )
    if result["status"] not in {"succeeded", "unknown"}:
        raise ValueError(
            f"Telephony provider rejected the call: {result['failure_code']}."
        )

    if context.misfired_count:
        logger.info(
            "Placed a scheduled call to %s late; %d earlier occurrence(s) were "
            "coalesced into this one.",
            to_number,
            context.misfired_count,
        )

    return {
        "to_number": to_number,
        "call_id": result["call_id"],
        "provider_call_id": result.get("call_sid"),
        "status": result["status"],
        "late_by_occurrences": context.misfired_count,
    }
