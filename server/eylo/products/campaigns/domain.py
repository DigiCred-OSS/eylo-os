"""Campaign definition errors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from eylo.common.revisions import DefinitionRevisionError


class CampaignDefinitionError(DefinitionRevisionError):
    """Base error for immutable campaign definition commands."""


class CampaignConflictError(CampaignDefinitionError):
    """A campaign command conflicts with its current immutable revision."""


class CampaignNotFoundError(CampaignDefinitionError):
    """No campaign or exact revision is reachable in caller scope."""


class CampaignPreparationIssueLevel(StrEnum):
    """Whether an issue is informational or prevents new work."""

    WARNING = "warning"
    BLOCKER = "blocker"


class CampaignPreparationIssueCode(StrEnum):
    """Stable UI-facing campaign preparation facts."""

    POLICY_NOT_EVALUATED = "policy_not_evaluated"
    PREFERENCES_NOT_ENFORCED = "preferences_not_enforced"
    INVALID_CHANNEL_ADDRESS = "invalid_channel_address"
    CONTACT_DELETION_PENDING = "contact_deletion_pending"


@dataclass(frozen=True, slots=True)
class CampaignPreparationIssue:
    """One aggregate preparation issue without contact PII."""

    code: CampaignPreparationIssueCode
    level: CampaignPreparationIssueLevel
    affected_contacts: int


@dataclass(frozen=True, slots=True)
class CampaignPreparation:
    """Read-only summary; it never selects or filters the audience."""

    selected_contacts: int
    issues: tuple[CampaignPreparationIssue, ...]

    @property
    def warning_facts(self) -> int:
        return sum(
            issue.affected_contacts
            for issue in self.issues
            if issue.level is CampaignPreparationIssueLevel.WARNING
        )

    @property
    def blocking_facts(self) -> int:
        return sum(
            issue.affected_contacts
            for issue in self.issues
            if issue.level is CampaignPreparationIssueLevel.BLOCKER
        )


__all__ = [
    "CampaignConflictError",
    "CampaignDefinitionError",
    "CampaignNotFoundError",
    "CampaignPreparation",
    "CampaignPreparationIssue",
    "CampaignPreparationIssueCode",
    "CampaignPreparationIssueLevel",
]
