"""WebRTC config catalog."""

from __future__ import annotations

from enum import Enum

__all__ = ["WebRTCProviders"]


class WebRTCProviders(str, Enum):
    METERED = "metered"
    TURNIX = "turnix"
