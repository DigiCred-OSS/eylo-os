"""Compose explicit sandbox authority with its execution adapter."""

from __future__ import annotations

from uuid import UUID

from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.sandbox_configs.catalog import SandboxProviders
from eylo.modules.sandbox_configs.domain import ResolvedSandbox
from eylo.modules.sandbox_configs.wiring import build_sandbox_config_resolver
from eylo.sockets.sandbox.base import SandboxVendorAdapter
from eylo.sockets.sandbox.vendors.docker import DockerSandboxAdapter

__all__ = [
    "build_sandbox_adapter",
    "resolve_pinned_sandbox_adapter",
    "resolve_sandbox_adapter",
]


def build_sandbox_adapter(resolved: ResolvedSandbox) -> SandboxVendorAdapter:
    if resolved.provider is SandboxProviders.DOCKER:
        return DockerSandboxAdapter(
            resolved.endpoint,
            labels={
                "eylo.organization": str(resolved.organization_id),
                "eylo.config": str(resolved.provider_config_id),
                "eylo.config_revision": str(resolved.provider_config_revision),
            },
        )
    raise _unsupported_provider()


async def resolve_sandbox_adapter(
    organization_id: UUID,
    *,
    provider_config_id: UUID,
    db=None,
) -> tuple[SandboxVendorAdapter, ResolvedSandbox]:
    """Build an adapter for one explicit ready config revision."""
    resolved = await build_sandbox_config_resolver(db).resolve(
        organization_id,
        provider_config_id=provider_config_id,
    )
    return build_sandbox_adapter(resolved), resolved


async def resolve_pinned_sandbox_adapter(
    organization_id: UUID,
    *,
    provider_config_id: UUID,
    provider_config_revision: int,
    db=None,
) -> tuple[SandboxVendorAdapter, ResolvedSandbox]:
    """Build an adapter from immutable authority held by existing work."""
    resolved = await build_sandbox_config_resolver(db).resolve_pinned(
        organization_id,
        provider_config_id=provider_config_id,
        revision=provider_config_revision,
    )
    return build_sandbox_adapter(resolved), resolved


def _unsupported_provider() -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.SANDBOX,
        missing=["supported_provider"],
        configure_via="/api/sandbox-configs",
    )
