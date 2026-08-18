"""Application contract for querying organization-owned Agents."""

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from eylo.modules.agents.models import AgentKind, AgentStatus


class AgentSortField(str, Enum):
    NAME = "name"
    STATUS = "status"
    KIND = "kind"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class AgentSortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class AgentListQuery:
    agent_ids: tuple[UUID, ...] = ()
    search: str | None = None
    statuses: tuple[AgentStatus, ...] = ()
    kinds: tuple[AgentKind, ...] = ()
    sort_by: AgentSortField = AgentSortField.UPDATED_AT
    sort_direction: AgentSortDirection = AgentSortDirection.DESC

    def __post_init__(self) -> None:
        if self.search is None:
            return

        normalized_search = self.search.strip()
        object.__setattr__(self, "search", normalized_search or None)
