"""Identifier helpers for UUID values crossing library boundaries."""

from __future__ import annotations

from typing import Any
from uuid import UUID


def is_uuid_utils_uuid(value: Any) -> bool:
    """Return True when value is a uuid_utils UUID instance."""
    return (
        value.__class__.__module__ == "uuid_utils"
        and value.__class__.__name__ == "UUID"
    )


def normalize_uuid_like(value: Any) -> Any:
    """Convert uuid_utils UUID values to stdlib UUID while preserving UUIDv7 value."""
    if isinstance(value, UUID):
        return value
    if is_uuid_utils_uuid(value):
        return UUID(str(value))
    return value


def as_stdlib_uuid(value: object) -> UUID:
    """Convert any UUID-like value to stdlib UUID."""
    normalized = normalize_uuid_like(value)
    if isinstance(normalized, UUID):
        return normalized
    return UUID(str(value))
