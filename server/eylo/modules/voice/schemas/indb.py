"""Data contracts for the `voice` domain."""

from __future__ import annotations

import uuid

from pydantic import ConfigDict, Field

from eylo.common.schemas import EyloBaseModelSchema
from eylo.modules.voice.schemas.api import VoiceConfig


class VoiceConfigBase(EyloBaseModelSchema):
    organization_id: uuid.UUID
    name: str
    description: str | None = None
    revision: int = Field(gt=0)
    config: VoiceConfig


class VoiceConfigInDb(VoiceConfigBase):
    model_config = ConfigDict(from_attributes=True)
