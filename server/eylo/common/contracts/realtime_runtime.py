"""Neutral resolved configuration consumed by Realtime socket factories."""

from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class ResolvedRealtimeConfig(Protocol):
    """Structural runtime values without a dependency on the domain model."""

    @property
    def provider_id(self) -> str: ...

    @property
    def config(self) -> Mapping[str, object]: ...

    @property
    def secrets(self) -> Mapping[str, str]: ...
