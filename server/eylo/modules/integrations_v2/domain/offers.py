"""What the curated registry offers, as a value the domain can reason about.

The registry lives in `pipelines/`, which the domain may not import. Rather than
reach upward, the module receives what it needs as a value object built by the
controller. `list_catalog(capabilities=...)` uses the same pattern for
capability gating.

This is what lets `install_vendor` fail closed on a tool this deployment does
not carry without the module knowing the registry exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from .enums import VendorAuthKind


@dataclass(frozen=True, slots=True)
class CuratedVendorOffer:
    """One vendor as the running deployment can actually execute it."""

    vendor: str
    supported_auth_kinds: frozenset[VendorAuthKind]
    wire_ids: frozenset[str]
    requires_instance_url: bool = False

    def __post_init__(self) -> None:
        if not self.vendor.strip():
            raise ValueError("Curated vendor offer requires a vendor id.")
        if not self.supported_auth_kinds:
            raise ValueError("Curated vendor offer requires at least one auth kind.")

    def supports(self, auth_kind: VendorAuthKind) -> bool:
        return auth_kind in self.supported_auth_kinds

    def carries(self, wire_id: str) -> bool:
        return wire_id in self.wire_ids


__all__ = ["CuratedVendorOffer"]
