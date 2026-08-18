"""In-process registry of curated vendors and their tools.

The registry is the single source of truth for what this deployment can
execute. Marketplace and Agent projections are synthesized from it rather than
maintained alongside it, which makes catalog/code drift structurally
impossible: a tool that is not registered cannot be offered or executed.

Registration happens at import time through `@curated_tool`. `load_vendors()`
imports the vendor packages so a process that only reads the registry does not
depend on some earlier import having happened by luck.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable

from pydantic import BaseModel

from eylo.modules.integrations_v2.domain.enums import ToolEffect

from .contracts import CuratedToolCallable, CuratedToolSpec, CuratedVendorSpec

_VENDOR_MODULES = (
    "airtable",
    "asana",
    "calendly",
    "confluence",
    "dropbox",
    "freshdesk",
    "github",
    "gitlab",
    "gmail",
    "googlecalendar",
    "googledocs",
    "googledrive",
    "googlesheets",
    "googletasks",
    "hubspot",
    "intercom",
    "jira",
    "linear",
    "notion",
    "outlook",
    "pagerduty",
    "pipedrive",
    "sentry",
    "shopify",
    "slack",
    "stripe",
    "typeform",
    "zendesk",
    "zoom",
)


class CuratedRegistry:
    """Vendors and tools this deployment carries."""

    def __init__(self) -> None:
        self._vendors: dict[str, CuratedVendorSpec] = {}
        self._tools: dict[str, CuratedToolSpec] = {}

    def register_vendor(self, spec: CuratedVendorSpec) -> CuratedVendorSpec:
        existing = self._vendors.get(spec.vendor)
        if existing is not None and existing != spec:
            raise ValueError(f"Vendor '{spec.vendor}' is already registered.")
        self._vendors[spec.vendor] = spec
        return spec

    def register_tool(self, spec: CuratedToolSpec) -> CuratedToolSpec:
        existing = self._tools.get(spec.wire_id)
        if existing is not None and existing.handler is not spec.handler:
            raise ValueError(f"Tool '{spec.wire_id}' is already registered.")
        self._tools[spec.wire_id] = spec
        return spec

    def vendor(self, vendor: str) -> CuratedVendorSpec | None:
        return self._vendors.get(vendor)

    def vendors(self) -> tuple[CuratedVendorSpec, ...]:
        return tuple(self._vendors[key] for key in sorted(self._vendors))

    def tool(self, wire_id: str) -> CuratedToolSpec | None:
        """Resolve one catalog binding to the callable that satisfies it."""
        return self._tools.get(wire_id)

    def tools_for(self, vendor: str) -> tuple[CuratedToolSpec, ...]:
        selected = [spec for spec in self._tools.values() if spec.vendor == vendor]
        return tuple(sorted(selected, key=lambda spec: spec.name))

    def wire_ids(self) -> frozenset[str]:
        return frozenset(self._tools)


registry = CuratedRegistry()


def curated_tool(
    *,
    vendor: str,
    name: str,
    display_name: str,
    description: str,
    input_model: type[BaseModel],
    effect: ToolEffect = ToolEffect.READ,
    scopes: Iterable[str] = (),
) -> Callable[[CuratedToolCallable], CuratedToolCallable]:
    """Declare one curated tool and register it under the running process.

    The decorated function keeps its identity, so a vendor module may call it
    directly from another curated tool without going back through the registry.
    """

    def decorator(handler: CuratedToolCallable) -> CuratedToolCallable:
        registry.register_tool(
            CuratedToolSpec(
                vendor=vendor,
                name=name,
                display_name=display_name,
                description=description,
                effect=effect,
                input_model=input_model,
                handler=handler,
                scopes=tuple(scopes),
            )
        )
        return handler

    return decorator


def load_vendors() -> CuratedRegistry:
    """Import every vendor package so the registry is fully populated."""
    for module in _VENDOR_MODULES:
        importlib.import_module(f"{__package__}.vendors.{module}.tools")
    return registry


__all__ = [
    "CuratedRegistry",
    "curated_tool",
    "load_vendors",
    "registry",
]
