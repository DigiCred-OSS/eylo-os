"""Widget feature-agent contracts."""

from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field

from .common import FrozenFrameworkModel, JsonObject


class FeatureArtifactKind(str, Enum):
    """Data produced by widget features."""

    SESSION_RECORDING = "session_recording"
    TRANSCRIPT = "transcript"
    FEEDBACK = "feedback"
    INTERACTION_SUMMARY = "interaction_summary"
    ANALYTICS_SAMPLE = "analytics_sample"


class FeatureSignalKind(str, Enum):
    """Feature lifecycle signal that can activate companion agents."""

    ARTIFACT_READY = "artifact_ready"
    FEATURE_ENABLED = "feature_enabled"
    FEATURE_DISABLED = "feature_disabled"


class FeatureAgentBinding(FrozenFrameworkModel):
    """Maps an enabled widget feature to companion agents."""

    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    feature_name: str
    agent_ids: tuple[UUID, ...]
    is_enabled: bool = True
    metadata: JsonObject = Field(default_factory=dict)


class FeatureArtifact(FrozenFrameworkModel):
    """Typed backend artifact created by a widget feature."""

    id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    feature_name: str
    kind: FeatureArtifactKind
    conversation_id: UUID | None = None
    contact_id: UUID | None = None
    uri: str | None = None
    payload: JsonObject = Field(default_factory=dict)
    metadata: JsonObject = Field(default_factory=dict)


class FeatureSignal(FrozenFrameworkModel):
    """Domain signal emitted when feature-agent work should react."""

    kind: FeatureSignalKind
    artifact_id: UUID | None = None
    binding_id: UUID | None = None
    organization_id: UUID
    metadata: JsonObject = Field(default_factory=dict)
