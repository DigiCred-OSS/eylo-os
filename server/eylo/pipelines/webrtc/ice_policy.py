"""Admission policy for remote WebRTC ICE candidates."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum


class IceDeploymentMode(str, Enum):
    """Network targets a deployment permits remote peers to nominate."""

    PUBLIC = "public"
    LOCAL = "local"


class IceCandidateError(ValueError):
    """A remote candidate is malformed or targets a forbidden network."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class RemoteIceCandidate:
    """Parsed fields needed to safely construct an aiortc candidate."""

    foundation: str
    component: int
    protocol: str
    priority: int
    address: str
    port: int
    candidate_type: str
    related_address: str | None = None
    related_port: int | None = None
    tcp_type: str | None = None


_LOCAL_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "fc00::/7",
        "::1/128",
    )
)


def parse_remote_candidate(
    candidate: str,
    *,
    mode: IceDeploymentMode,
) -> RemoteIceCandidate:
    """Parse one candidate and enforce the deployment network boundary."""
    if len(candidate) > 2048:
        raise IceCandidateError("malformed_candidate")
    normalized = candidate.removeprefix("a=")
    parts = normalized.split()
    if (
        len(parts) < 8
        or not parts[0].startswith("candidate:")
        or parts[6].lower() != "typ"
    ):
        raise IceCandidateError("malformed_candidate")

    foundation = parts[0].partition(":")[2]
    protocol = parts[2].lower()
    candidate_type = parts[7].lower()
    if not foundation or protocol not in {"tcp", "udp"}:
        raise IceCandidateError("unsupported_candidate")
    if candidate_type not in {"host", "srflx", "prflx", "relay"}:
        raise IceCandidateError("unsupported_candidate")

    try:
        component = int(parts[1])
        priority = int(parts[3])
        port = int(parts[5])
    except ValueError:
        raise IceCandidateError("malformed_candidate") from None
    if component not in {1, 2} or priority < 0 or not 1 <= port <= 65535:
        raise IceCandidateError("malformed_candidate")

    address = parts[4].lower().rstrip(".")
    _enforce_address(address, mode=mode)
    extensions = {
        parts[index].lower(): parts[index + 1] for index in range(8, len(parts) - 1, 2)
    }
    related_port: int | None = None
    if "rport" in extensions:
        try:
            related_port = int(extensions["rport"])
        except ValueError:
            raise IceCandidateError("malformed_candidate") from None
        if not 1 <= related_port <= 65535:
            raise IceCandidateError("malformed_candidate")
    tcp_type = extensions.get("tcptype")
    if protocol == "tcp" and tcp_type not in {"active", "passive", "so"}:
        raise IceCandidateError("malformed_candidate")
    return RemoteIceCandidate(
        foundation=foundation,
        component=component,
        protocol=protocol,
        priority=priority,
        address=address,
        port=port,
        candidate_type=candidate_type,
        related_address=extensions.get("raddr"),
        related_port=related_port,
        tcp_type=tcp_type,
    )


def filter_offer_candidates(
    sdp: str,
    *,
    mode: IceDeploymentMode,
    max_candidates: int = 128,
) -> str:
    """Remove forbidden embedded candidates and reject an unusable offer."""
    kept: list[str] = []
    candidate_count = 0
    accepted_count = 0
    for line in sdp.splitlines():
        if not line.startswith("a=candidate:"):
            kept.append(line)
            continue
        candidate_count += 1
        if candidate_count > max_candidates:
            raise IceCandidateError("candidate_limit_reached")
        try:
            parse_remote_candidate(line, mode=mode)
        except IceCandidateError:
            continue
        accepted_count += 1
        kept.append(line)

    if candidate_count and not accepted_count:
        raise IceCandidateError("no_permitted_candidates")
    return "\r\n".join(kept) + "\r\n"


def _enforce_address(address: str, *, mode: IceDeploymentMode) -> None:
    if address.endswith(".local"):
        if mode is IceDeploymentMode.LOCAL:
            return
        raise IceCandidateError("non_public_candidate")

    try:
        target = ipaddress.ip_address(address)
    except ValueError:
        raise IceCandidateError("hostname_candidate_rejected") from None

    if target.is_unspecified or target.is_multicast:
        raise IceCandidateError("unsafe_candidate")
    if target == ipaddress.ip_address("169.254.169.254"):
        raise IceCandidateError("unsafe_candidate")
    if target.is_global:
        return
    if mode is IceDeploymentMode.LOCAL and any(
        target in network for network in _LOCAL_NETWORKS
    ):
        return
    raise IceCandidateError("non_public_candidate")
