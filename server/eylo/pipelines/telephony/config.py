"""Translate validated telephony domain config into the socket contract."""

from __future__ import annotations

from eylo.modules.telephony.provider_config_domain import TelephonyProviderConfig
from eylo.sockets.telephony.base import TelephonyConfig, TelephonyProvider


def build_telephony_runtime_config(
    config: TelephonyProviderConfig,
) -> TelephonyConfig:
    return TelephonyConfig(
        provider=TelephonyProvider(config.provider.value),
        extra_config=config.adapter_settings(),
    )
