"""Typed member collection query owned by the members domain."""

from dataclasses import dataclass
from enum import StrEnum

from eylo.modules.members.models import MemberStatus


class MemberSortField(StrEnum):
    NAME = "name"
    EMAIL = "email"
    STATUS = "status"
    LAST_LOGIN = "last_login"
    CREATED_AT = "created_at"


class MemberSortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True)
class MemberListQuery:
    search: str | None = None
    statuses: tuple[MemberStatus, ...] = ()
    sort_by: MemberSortField = MemberSortField.CREATED_AT
    sort_direction: MemberSortDirection = MemberSortDirection.DESC
