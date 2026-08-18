"""Persistence access for the `voice` domain."""

from eylo.common.repositories import BaseORMRepository
from eylo.modules.voice.models import VoiceConfigModel


class VoiceConfigRepository(BaseORMRepository[VoiceConfigModel]):
    @property
    def model(self) -> type[VoiceConfigModel]:
        return VoiceConfigModel
