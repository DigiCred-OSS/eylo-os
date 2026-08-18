"""Request and response shapes for schedules."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from eylo.common.contracts.scheduler import MisfirePolicy
from eylo.modules.agent_runs.domain import AgentRunLifecycle, AgentRunOutcome


class ScheduleDefinitionRequest(BaseModel):
    """Complete semantic definition used by create and explicit update.

    `timezone` has no default, and that is the single most consequential field
    here. "Every morning at 9" is not a UTC statement — it means 9am where the
    person is, and it has to survive daylight saving. A default of UTC would be
    silently wrong for most of the world, twice a year, for every recurring
    schedule.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=256)
    action: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    agent_id: uuid.UUID = Field(
        description=(
            "Agent whose current published revision is pinned by this explicit "
            "create/update. Every schedule triggers an agent; there is no "
            "platform/default executor."
        ),
    )

    timezone: str = Field(
        description="IANA name, e.g. 'Europe/Berlin'. Occurrences are computed in it."
    )
    starts_at: datetime = Field(description="The anchor. Also the wall-clock time each occurrence lands on.")
    rule: str | None = Field(
        default=None,
        description=(
            "RFC 5545 RRULE without DTSTART, e.g. 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR'. "
            "Omit for a one-shot."
        ),
    )
    ends_at: datetime | None = None
    misfire_policy: MisfirePolicy = MisfirePolicy.COALESCE


class ScheduleCreate(ScheduleDefinitionRequest):
    key: str = Field(
        min_length=1,
        max_length=128,
        description=(
            "Stable id, unique per organization. Re-creating this key is a "
            "conflict; use the explicit expected-revision update endpoint."
        ),
    )


class ScheduleUpdate(ScheduleDefinitionRequest):
    expected_revision: int = Field(ge=1)


class ScheduleRevisionRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2000)


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    key: str
    name: str
    action: str
    payload: dict[str, Any]
    rule: str | None
    timezone: str
    starts_at: datetime
    ends_at: datetime | None
    misfire_policy: MisfirePolicy
    enabled: bool
    published_revision: int
    lifecycle: str
    agent_id: uuid.UUID
    agent_revision: int
    next_at: datetime | None
    last_fired_at: datetime | None
    retired_at: datetime | None
    last_error: str | None


class ScheduleRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: uuid.UUID
    schedule_id: uuid.UUID
    schedule_revision: int
    agent_id: uuid.UUID
    agent_revision: int
    scheduled_for: datetime
    action: str
    agent_run_id: uuid.UUID
    lifecycle: AgentRunLifecycle
    outcome: AgentRunOutcome | None
    # Non-zero means the scheduler was not running when earlier occurrences
    # came due. Surfaced because an operator seeing a late run should be able
    # to tell "we were down" from "the rule is wrong".
    misfired_count: int
    started_at: datetime | None
    finished_at: datetime | None
    result: dict[str, Any] | None
    failure_summary: str | None
