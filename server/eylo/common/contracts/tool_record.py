"""Minimal tool record contract consumed by vendor adapters."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from eylo.common.contracts.tool_platform import PlatformTool


@runtime_checkable
class ToolRecord(Protocol):
    """Structural view of a persisted tool required by vendor adapters."""

    @property
    def id(self) -> UUID: ...

    @property
    def llm_config(self) -> PlatformTool: ...
