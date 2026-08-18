"""Shared types for the Eylo agent framework contracts."""

from __future__ import annotations

from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict

JsonObject: TypeAlias = dict[str, object]


class FrameworkModel(BaseModel):
    """Base model for mutable framework state."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


class FrozenFrameworkModel(BaseModel):
    """Base model for immutable framework value objects."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )


class FrameworkMetadata(BaseModel):
    """Platform metadata envelope for framework primitives.

    Framework metadata is schema-backed. Subsystems should define focused
    subclasses for known fields; this base remains extensible so older persisted
    metadata and integration-provided annotations can round-trip safely.
    """

    model_config = ConfigDict(
        extra="allow",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.__class__.model_fields:
            return getattr(self, key)
        if self.model_extra and key in self.model_extra:
            return self.model_extra[key]
        return default

    def __contains__(self, key: str) -> bool:
        return key in self.__class__.model_fields or bool(
            self.model_extra and key in self.model_extra
        )

    def __getitem__(self, key: str) -> Any:
        if key not in self:
            raise KeyError(key)
        return self.get(key)
