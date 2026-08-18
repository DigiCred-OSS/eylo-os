"""Realtime adapter selection with explicitly resolved realtime credentials."""

from __future__ import annotations

from eylo.common.config import settings
from eylo.common.contracts.provider_config import Capability, NotConfiguredError
from eylo.common.contracts.realtime_runtime import ResolvedRealtimeConfig
from eylo.sockets.realtime.base import RealtimeAdapter
from eylo.sockets.realtime.config import RealtimeSessionConfig


class RealtimeFactory:
    @staticmethod
    def validate(vendor: str, resolved: ResolvedRealtimeConfig) -> None:
        if not settings.ENABLE_REALTIME_VOICE:
            raise ValueError("Realtime voice is disabled (ENABLE_REALTIME_VOICE=false)")
        if vendor != resolved.provider_id:
            raise _not_configured("compatible_realtime_provider")
        if vendor == "amazon-nova-sonic":
            _aws_credentials(resolved)
        else:
            _api_key(resolved)

    @staticmethod
    def create(
        config: RealtimeSessionConfig,
        resolved: ResolvedRealtimeConfig,
    ) -> RealtimeAdapter:
        RealtimeFactory.validate(config.vendor, resolved)

        if config.vendor == "amazon-nova-sonic":
            from eylo.sockets.realtime.vendors.amazon_nova_sonic import (
                AmazonNovaSonicAdapter,
            )

            access_key_id, secret_access_key, session_token = _aws_credentials(
                resolved
            )
            region = resolved.config.get("region")
            if not isinstance(region, str) or not region:
                raise _not_configured("region")
            return AmazonNovaSonicAdapter(
                config,
                region=region,
                access_key_id=access_key_id,
                secret_access_key=secret_access_key,
                session_token=session_token,
            )
        if config.vendor == "gemini-live":
            from eylo.sockets.realtime.vendors.gemini_live import GeminiLiveAdapter

            return GeminiLiveAdapter(config, api_key=_api_key(resolved))
        if config.vendor == "openai-realtime":
            from eylo.sockets.realtime.vendors.openai_realtime import (
                OpenAIRealtimeAdapter,
            )

            return OpenAIRealtimeAdapter(config, api_key=_api_key(resolved))
        raise AssertionError("validated realtime vendor was not handled")


def _api_key(resolved: ResolvedRealtimeConfig) -> str:
    api_key = resolved.secrets.get("api_key")
    if not api_key:
        raise _not_configured("credentials")
    return api_key


def _aws_credentials(
    resolved: ResolvedRealtimeConfig,
) -> tuple[str, str, str | None]:
    access_key_id = resolved.secrets.get("access_key_id")
    secret_access_key = resolved.secrets.get("secret_access_key")
    if not access_key_id or not secret_access_key:
        raise _not_configured("credentials")
    return access_key_id, secret_access_key, resolved.secrets.get("session_token")


def _not_configured(missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.REALTIME,
        missing=[missing],
        configure_via="/api/realtime-configs",
    )
