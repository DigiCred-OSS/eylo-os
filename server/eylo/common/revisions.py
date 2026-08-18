"""Shared value objects for domain-owned immutable definition revisions.

This module supplies vocabulary and lifecycle rules only. Each executable
domain owns its typed header, revision payload, repository, and publication
validation; there is deliberately no generic definition registry.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from uuid import UUID

import uuid_utils

MAX_REVOCATION_REASON_LENGTH = 2_000


class DefinitionRevisionError(Exception):
    """Base error for executable-definition lifecycle operations."""


class InvalidDefinitionRevisionError(DefinitionRevisionError):
    """Raised when revision state violates a domain-independent invariant."""


class DefinitionNotPublishedError(DefinitionRevisionError):
    """Raised when a mutable draft is selected for product execution."""


class DefinitionWithdrawnError(DefinitionRevisionError):
    """Raised when a withdrawn header is selected for new work."""


class DefinitionRevokedError(DefinitionRevisionError):
    """Raised when an emergency-revoked revision is selected or resumed."""


class RevisionConflictError(DefinitionRevisionError):
    """Raised when an optimistic revision command observes stale state."""

    def __init__(self, *, expected: int, actual: int) -> None:
        self.expected = _positive_revision(expected, field_name="expected")
        self.actual = _positive_revision(actual, field_name="actual")
        super().__init__(
            f"Definition revision conflict: expected {self.expected}, "
            f"found {self.actual}."
        )


class DefinitionLifecycle(str, Enum):
    """Lifecycle of a stable definition header and its published alias."""

    DRAFT = "draft"
    PUBLISHED = "published"
    WITHDRAWN = "withdrawn"
    ARCHIVED = "archived"


class RevisionAvailability(str, Enum):
    """Availability of an immutable revision.

    Ordinary withdrawal belongs to the stable header so already pinned work can
    continue. Emergency revocation belongs to the exact revision and blocks
    both new selection and pinned resume.
    """

    PUBLISHED = "published"
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class DefinitionRef:
    """Exact immutable reference stored by filed work and other definitions."""

    definition_id: UUID
    revision: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definition_id",
            _uuid(self.definition_id, field_name="definition_id"),
        )
        object.__setattr__(self, "revision", _positive_revision(self.revision))


@dataclass(frozen=True, slots=True)
class DefinitionHeaderState:
    """Domain-independent state of a stable header and mutable draft."""

    lifecycle: DefinitionLifecycle = DefinitionLifecycle.DRAFT
    published_revision: int | None = None
    draft_version: int = 1
    draft_dirty: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "lifecycle", DefinitionLifecycle(self.lifecycle))
        object.__setattr__(
            self,
            "draft_version",
            _positive_revision(self.draft_version, field_name="draft_version"),
        )
        if self.published_revision is not None:
            object.__setattr__(
                self,
                "published_revision",
                _positive_revision(
                    self.published_revision,
                    field_name="published_revision",
                ),
            )
        if self.lifecycle is DefinitionLifecycle.DRAFT and (
            self.published_revision is not None or not self.draft_dirty
        ):
            raise InvalidDefinitionRevisionError(
                "A draft-only header cannot expose a published revision."
            )
        if self.lifecycle is not DefinitionLifecycle.DRAFT and (
            self.published_revision is None
        ):
            raise InvalidDefinitionRevisionError(
                "A non-draft header must retain a published revision."
            )

    def edit(self, *, expected_draft_version: int) -> DefinitionHeaderState:
        self._require_draft_version(expected_draft_version)
        if self.lifecycle is DefinitionLifecycle.ARCHIVED:
            raise DefinitionWithdrawnError("Archived definitions cannot be edited.")
        return replace(
            self,
            draft_version=self.draft_version + 1,
            draft_dirty=True,
        )

    def publish(
        self,
        *,
        revision: int,
        expected_draft_version: int,
    ) -> DefinitionHeaderState:
        self._require_draft_version(expected_draft_version)
        revision = _positive_revision(revision)
        expected_revision = (self.published_revision or 0) + 1
        if revision != expected_revision:
            raise RevisionConflictError(
                expected=expected_revision,
                actual=revision,
            )
        if not self.draft_dirty:
            raise InvalidDefinitionRevisionError(
                "Publishing requires a changed or new draft."
            )
        if self.lifecycle is DefinitionLifecycle.ARCHIVED:
            raise DefinitionWithdrawnError("Archived definitions cannot be published.")
        return replace(
            self,
            lifecycle=DefinitionLifecycle.PUBLISHED,
            published_revision=revision,
            draft_dirty=False,
        )

    def withdraw(self) -> DefinitionHeaderState:
        if self.published_revision is None:
            raise DefinitionNotPublishedError(
                "A draft-only definition cannot be withdrawn."
            )
        if self.lifecycle is DefinitionLifecycle.ARCHIVED:
            raise DefinitionWithdrawnError("Archived definitions cannot be withdrawn.")
        return replace(self, lifecycle=DefinitionLifecycle.WITHDRAWN)

    def archive(self) -> DefinitionHeaderState:
        if self.published_revision is None:
            raise DefinitionNotPublishedError(
                "A draft-only definition cannot be archived."
            )
        return replace(self, lifecycle=DefinitionLifecycle.ARCHIVED)

    def revision_for_new_work(self) -> int:
        if self.lifecycle is DefinitionLifecycle.DRAFT:
            raise DefinitionNotPublishedError(
                "A draft definition cannot be used for product execution."
            )
        if self.lifecycle is not DefinitionLifecycle.PUBLISHED:
            raise DefinitionWithdrawnError(
                "A withdrawn definition cannot start new work."
            )
        if self.published_revision is None:  # guarded by construction
            raise DefinitionNotPublishedError("Definition has no published revision.")
        return self.published_revision

    def _require_draft_version(self, expected: int) -> None:
        expected = _positive_revision(expected, field_name="expected_draft_version")
        if expected != self.draft_version:
            raise RevisionConflictError(expected=expected, actual=self.draft_version)


@dataclass(frozen=True, slots=True)
class PublishedRevisionState:
    """Lifecycle metadata allowed beside an immutable revision payload."""

    published_at: datetime
    availability: RevisionAvailability = RevisionAvailability.PUBLISHED
    revoked_at: datetime | None = None
    revoked_by: UUID | None = None
    revocation_reason: str | None = None
    cancellation_requested_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "availability",
            RevisionAvailability(self.availability),
        )
        _aware_datetime(self.published_at, field_name="published_at")
        lifecycle_values = (
            self.revoked_at,
            self.revoked_by,
            self.revocation_reason,
            self.cancellation_requested_at,
        )
        if self.availability is RevisionAvailability.PUBLISHED:
            if any(value is not None for value in lifecycle_values):
                raise InvalidDefinitionRevisionError(
                    "A published revision cannot carry revocation metadata."
                )
            return
        if any(value is None for value in lifecycle_values):
            raise InvalidDefinitionRevisionError(
                "A revoked revision requires actor, time, reason, and cancellation request."
            )
        object.__setattr__(
            self,
            "revoked_by",
            _uuid(self.revoked_by, field_name="revoked_by"),
        )
        _aware_datetime(self.revoked_at, field_name="revoked_at")
        _aware_datetime(
            self.cancellation_requested_at,
            field_name="cancellation_requested_at",
        )
        _revocation_reason(self.revocation_reason)

    def require_available(self) -> None:
        if self.availability is RevisionAvailability.REVOKED:
            raise DefinitionRevokedError(
                "The executable definition revision was emergency-revoked."
            )

    def revoke(
        self,
        *,
        actor_id: UUID,
        reason: str,
        at: datetime,
    ) -> PublishedRevisionState:
        self.require_available()
        actor_id = _uuid(actor_id, field_name="actor_id")
        reason = _revocation_reason(reason)
        at = _aware_datetime(at, field_name="revoked_at")
        return replace(
            self,
            availability=RevisionAvailability.REVOKED,
            revoked_at=at,
            revoked_by=actor_id,
            revocation_reason=reason,
            cancellation_requested_at=at,
        )


def _positive_revision(value: int, *, field_name: str = "revision") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InvalidDefinitionRevisionError(
            f"{field_name.replace('_', ' ').capitalize()} must be a positive integer."
        )
    return value


def _uuid(value: object, *, field_name: str) -> UUID:
    if not isinstance(value, UUID | uuid_utils.UUID):
        raise InvalidDefinitionRevisionError(
            f"{field_name.replace('_', ' ').capitalize()} must be a UUID."
        )
    return value if isinstance(value, UUID) else UUID(str(value))


def _aware_datetime(value: datetime | None, *, field_name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise InvalidDefinitionRevisionError(
            f"{field_name.replace('_', ' ').capitalize()} must be timezone-aware."
        )
    return value


def _revocation_reason(value: str | None) -> str:
    if not isinstance(value, str):
        raise InvalidDefinitionRevisionError("Revocation reason must be text.")
    value = value.strip()
    if not value or len(value) > MAX_REVOCATION_REASON_LENGTH:
        raise InvalidDefinitionRevisionError(
            "Revocation reason must contain 1 to "
            f"{MAX_REVOCATION_REASON_LENGTH} characters."
        )
    return value


__all__ = [
    "DefinitionHeaderState",
    "DefinitionLifecycle",
    "DefinitionNotPublishedError",
    "DefinitionRef",
    "DefinitionRevokedError",
    "DefinitionRevisionError",
    "DefinitionWithdrawnError",
    "InvalidDefinitionRevisionError",
    "MAX_REVOCATION_REASON_LENGTH",
    "PublishedRevisionState",
    "RevisionAvailability",
    "RevisionConflictError",
]
