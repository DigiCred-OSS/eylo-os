"""Data contracts for the `provider_configs` domain."""

from pydantic import BaseModel, ConfigDict


class CapabilityStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    verified: bool
    ready: bool
    providers: list[str]


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: CapabilityStatusResponse
    stt: CapabilityStatusResponse
    tts: CapabilityStatusResponse
    realtime: CapabilityStatusResponse
    webrtc: CapabilityStatusResponse
    telephony: CapabilityStatusResponse
    email: CapabilityStatusResponse
    storage: CapabilityStatusResponse
    memory: CapabilityStatusResponse
    embedding: CapabilityStatusResponse
    reranking: CapabilityStatusResponse
    sandbox: CapabilityStatusResponse
