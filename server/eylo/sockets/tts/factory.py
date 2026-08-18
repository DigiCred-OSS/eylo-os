"""Adapter construction for the `tts` socket."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Literal, Optional, Union

from eylo.common.contracts.provider_config import Capability, NotConfiguredError
from eylo.sockets.tts.adapters.amazon_polly_adapter import AmazonPollyTTSAdapter
from eylo.sockets.tts.adapters.cartesia_contract_adapter import (
    CartesiaContractAdapter,
)
from eylo.sockets.tts.adapters.deepgram_adapter import (
    DeepgramTTSAdapter,
    DeepgramTTSConfig,
)
from eylo.sockets.tts.adapters.elevenlabs_adapter import ElevenLabsTTSAdapter
from eylo.sockets.tts.adapters.groq_adapter import GroqTTSAdapter, GroqTTSConfig
from eylo.sockets.tts.adapters.hume_adapter import HumeTTSAdapter, HumeTTSConfig
from eylo.sockets.tts.adapters.murf_adapter import MurfTTSAdapter, MurfTTSConfig
from eylo.sockets.tts.adapters.openai_adapter import OpenAITTSAdapter, OpenAITTSConfig
from eylo.sockets.tts.adapters.rime_adapter import RimeTTSAdapter, RimeTTSConfig
from eylo.sockets.tts.adapters.sarvam_contract_adapter import SarvamContractAdapter
from eylo.sockets.tts.adapters.smallest_adapter import (
    SmallestTTSAdapter,
    SmallestTTSConfig,
)
from eylo.sockets.tts.exceptions import TTSConnectionFailed
from eylo.sockets.tts.schemas import TTSConfig, normalize_tts_config

# Every configured TTS provider reaches one contract adapter through this union.
TTSService = Union[
    AmazonPollyTTSAdapter,
    ElevenLabsTTSAdapter,
    CartesiaContractAdapter,
    SarvamContractAdapter,
    OpenAITTSAdapter,
    DeepgramTTSAdapter,
    GroqTTSAdapter,
    RimeTTSAdapter,
    SmallestTTSAdapter,
    HumeTTSAdapter,
    MurfTTSAdapter,
]

TTSVendor = Literal[
    "amazon-polly",
    "elevenlabs",
    "cartesia",
    "sarvam",
    "openai",
    "deepgram",
    "groq",
    "rime",
    "smallest",
    "hume",
    "murf",
]

logger = logging.getLogger(__name__)

_REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "amazon-polly": frozenset(
        {
            "region",
            "model",
            "voice",
            "language",
            "access_key_id",
            "secret_access_key",
        }
    ),
    "cartesia": frozenset({"model", "voice", "api_key"}),
    "deepgram": frozenset({"model", "api_key"}),
    "elevenlabs": frozenset({"model", "voice", "api_key"}),
    "groq": frozenset({"model", "voice", "api_key"}),
    "hume": frozenset({"model", "language", "api_key"}),
    "murf": frozenset({"voice", "api_key"}),
    "openai": frozenset({"model", "voice", "api_key"}),
    "rime": frozenset({"model", "voice", "api_key"}),
    "sarvam": frozenset({"model", "voice", "language", "api_key"}),
    "smallest": frozenset({"model", "voice", "language", "api_key"}),
}


class TTSFactory:
    def __init__(
        self,
        tts_vendor: TTSVendor | str,
        tts_config: TTSConfig | dict[str, Any] | None = None,
        *,
        api_key: str | None = None,
    ):
        self._typed_config = normalize_tts_config(tts_config, vendor=tts_vendor)
        self._tts_vendor = (
            self._typed_config.vendor.value
            if hasattr(self._typed_config.vendor, "value")
            else self._typed_config.vendor
        )
        self._tts_config = self._typed_config.to_adapter_config()
        if api_key is not None:
            self._tts_config["api_key"] = api_key
        _require_configuration(self._tts_vendor, self._tts_config)
        self._tts_service: Optional[TTSService] = None

    def _contract_config(self) -> TTSConfig:
        """The unified config a contract adapter expects.

        `_typed_config` is already a `TTSConfig`; the only work here is moving
        vendor-specific settings into `options`, which is where the contract
        says they live.

        The promotion is one rule rather than a table per vendor: anything the
        caller supplied that is not a field of `TTSConfig` is vendor-specific
        by definition, and each adapter picks out the keys it knows. A per-
        vendor mapping would have to be extended for every new adapter, and the
        symptom of forgetting is a silently ignored setting — the exact class of
        bug this migration exists to remove.
        """
        config = self._typed_config
        known = set(TTSConfig.model_fields)
        options = dict(config.options)
        for key, value in self._tts_config.items():
            # `options` itself is not a vendor setting, and a field of the
            # contract belongs on the contract rather than duplicated beneath it.
            if key in known or key == "options" or value is None:
                continue
            options.setdefault(key, value)
        return config.model_copy(update={"options": options})

    def create_tts(self) -> TTSService:
        if self._tts_vendor == "amazon-polly":
            return AmazonPollyTTSAdapter(self._contract_config())
        elif self._tts_vendor == "elevenlabs":
            return ElevenLabsTTSAdapter(self._contract_config())
        elif self._tts_vendor == "cartesia":
            return CartesiaContractAdapter(self._contract_config())
        elif self._tts_vendor == "sarvam":
            return SarvamContractAdapter(self._contract_config())
        elif self._tts_vendor == "openai":
            return OpenAITTSAdapter(config=OpenAITTSConfig(**self._tts_config))
        elif self._tts_vendor == "deepgram":
            return DeepgramTTSAdapter(config=DeepgramTTSConfig(**self._tts_config))
        elif self._tts_vendor == "groq":
            return GroqTTSAdapter(config=GroqTTSConfig(**self._tts_config))
        elif self._tts_vendor == "rime":
            return RimeTTSAdapter(config=RimeTTSConfig(**self._tts_config))
        elif self._tts_vendor == "smallest":
            return SmallestTTSAdapter(config=SmallestTTSConfig(**self._tts_config))
        elif self._tts_vendor == "hume":
            return HumeTTSAdapter(config=HumeTTSConfig(**self._tts_config))
        elif self._tts_vendor == "murf":
            return MurfTTSAdapter(config=MurfTTSConfig(**self._tts_config))
        else:
            raise ValueError(f"Unsupported TTS vendor: {self._tts_vendor}")

    def initialize_agent(self) -> TTSService:
        """Initialize the TTS service."""
        if not self._tts_service:
            self._tts_service = self.create_tts()
        return self._tts_service

    @property
    def service(self) -> TTSService:
        """Get the current TTS service, initializing if needed."""
        if self._tts_service:
            return self._tts_service
        return self.initialize_agent()

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[TTSService, None]:
        """Establish a connection to the TTS service.

        For WebSocket vendors (Cartesia, ElevenLabs, Sarvam, Deepgram):
            Establishes persistent WS connection.
        For HTTP vendors (OpenAI):
            Validates API reachability with a probe request.

        Raises TTSConnectionFailed if connection cannot be established.
        """
        retry = self._typed_config.retry
        last_error: Exception | None = None
        for attempt in range(retry.max_retries + 1):
            try:
                ws = await self.service.connect()
                break
            except TTSConnectionFailed as error:
                last_error = error
                if attempt >= retry.max_retries:
                    raise TTSConnectionFailed("TTS connection failed.") from error
                logger.warning(
                    "TTS connection failed vendor=%s retry=%s/%s error_type=%s",
                    self._tts_vendor,
                    attempt + 1,
                    retry.max_retries,
                    type(error).__name__,
                )
                await asyncio.sleep(retry.retry_interval_seconds)
        else:
            raise TTSConnectionFailed("TTS connection failed.") from last_error
        try:
            yield ws
        finally:
            await self.service.disconnect()


def _require_configuration(vendor: str, config: dict[str, Any]) -> None:
    required = _REQUIRED_FIELDS.get(vendor)
    if required is None:
        return
    missing = {
        name
        for name in required
        if not isinstance(config.get(name), str) or not config[name].strip()
    }
    if vendor == "hume" and not any(
        isinstance(config.get(name), str) and config[name].strip()
        for name in ("voice", "voice_description")
    ):
        missing.add("voice")
    if missing:
        raise NotConfiguredError(
            capability=Capability.TTS,
            missing=sorted(missing),
            configure_via="/api/tts-configs",
        )
