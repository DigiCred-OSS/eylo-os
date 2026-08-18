"""Typed contracts for immutable executable agent definitions."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol
from uuid import UUID

from eylo.common.revisions import DefinitionRef
from eylo.modules.agents.schemas.indb import AgentInDb
from eylo.modules.templates.domain import TemplateConsumerKind, TemplateSegment
from eylo.modules.tools.schemas.indb import ToolInDb


class InvalidAgentDefinitionError(ValueError):
    """Raised when a draft cannot become a complete executable revision."""


class InvalidSwarmDefinitionError(ValueError):
    """Raised when a swarm draft cannot become an executable topology."""


class SwarmNotFoundError(LookupError):
    """Raised for missing or foreign swarm identity without disclosing which."""


class SwarmMemberNotFoundError(LookupError):
    """Raised when an organization-owned agent/member cannot be selected."""


@dataclass(frozen=True, slots=True)
class ResolvedExecutableAgent:
    """One exact agent revision ready for any supported runtime."""

    ref: DefinitionRef
    agent: AgentInDb
    consumer_kind: TemplateConsumerKind
    system_prompt: str | None
    prompt_segments: tuple[TemplateSegment, ...]
    tools: tuple[ToolInDb, ...]
    background_agents: tuple[DefinitionRef, ...]
    voice_config: Mapping[str, object] | None

    def __post_init__(self) -> None:
        if self.agent.id != self.ref.definition_id:
            raise InvalidAgentDefinitionError(
                "Resolved agent identity does not match its exact revision ref."
            )
        if self.agent.published_revision != self.ref.revision:
            raise InvalidAgentDefinitionError(
                "Resolved agent payload does not match its exact revision ref."
            )
        if self.voice_config is not None:
            object.__setattr__(
                self,
                "voice_config",
                MappingProxyType(dict(self.voice_config)),
            )


class ResolveExecutableAgent(Protocol):
    """Port shared by conversation, voice, background, sandbox, and schedule runs."""

    async def resolve_exact(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        revision: int,
        consumer_kind: TemplateConsumerKind,
    ) -> ResolvedExecutableAgent: ...

    async def resolve_for_new_work(
        self,
        *,
        organization_id: UUID,
        agent_id: UUID,
        consumer_kind: TemplateConsumerKind,
    ) -> ResolvedExecutableAgent: ...


@dataclass(frozen=True, slots=True)
class ResolvedSwarmMember:
    """One exact executable agent authorized by a topology revision."""

    executable_agent: ResolvedExecutableAgent
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedSwarmTopology:
    """One immutable swarm topology plus its exact executable members."""

    ref: DefinitionRef
    organization_id: UUID
    name: str
    slug: str
    description: str | None
    members: tuple[ResolvedSwarmMember, ...]

    def __post_init__(self) -> None:
        if not self.members:
            raise InvalidSwarmDefinitionError(
                "A published swarm topology requires at least one member."
            )
        member_ids = [
            member.executable_agent.ref.definition_id for member in self.members
        ]
        if len(member_ids) != len(set(member_ids)):
            raise InvalidSwarmDefinitionError(
                "A swarm topology cannot contain the same agent twice."
            )
        if any(
            member.executable_agent.agent.organization_id != self.organization_id
            for member in self.members
        ):
            raise InvalidSwarmDefinitionError(
                "Every swarm member must belong to the topology organization."
            )

    def member_by_agent_id(self, agent_id: UUID) -> ResolvedSwarmMember | None:
        return next(
            (
                member
                for member in self.members
                if member.executable_agent.ref.definition_id == agent_id
            ),
            None,
        )

    def member_by_slug(self, slug: str) -> ResolvedSwarmMember | None:
        return next(
            (
                member
                for member in self.members
                if member.executable_agent.agent.slug == slug
            ),
            None,
        )


class ResolveExecutableSwarm(Protocol):
    """Port for current-published selection and exact topology resolution."""

    async def resolve_exact(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
        revision: int,
        consumer_kind: TemplateConsumerKind,
    ) -> ResolvedSwarmTopology: ...

    async def resolve_for_new_work(
        self,
        *,
        organization_id: UUID,
        swarm_id: UUID,
        consumer_kind: TemplateConsumerKind,
    ) -> ResolvedSwarmTopology: ...

__all__ = [
    "InvalidAgentDefinitionError",
    "InvalidSwarmDefinitionError",
    "ResolveExecutableAgent",
    "ResolveExecutableSwarm",
    "ResolvedExecutableAgent",
    "ResolvedSwarmMember",
    "ResolvedSwarmTopology",
    "SwarmMemberNotFoundError",
    "SwarmNotFoundError",
]
