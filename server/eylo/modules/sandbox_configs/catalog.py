"""Sandbox config catalog."""

from __future__ import annotations

from enum import Enum

__all__ = ["SandboxProviders"]


class SandboxProviders(str, Enum):
    # The runtime every operator can already run. Isolation is a container
    # boundary — strong against an agent being talked into something hostile,
    # weak against a targeted kernel exploit. See `sockets/sandbox/vendors/`.
    DOCKER = "docker"
