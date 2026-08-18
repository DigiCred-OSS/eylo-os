"""Effective configuration resolution for the `llm_configs` domain."""

from collections.abc import Mapping
from uuid import UUID

from eylo.modules.llm_configs.domain import (
    InvalidLLMConfig,
    LLMOverrides,
    ResolvedLLM,
)
from eylo.modules.llm_configs.service import (
    LLMConfigService,
    effective_to_llm_provider_config,
)
from eylo.modules.provider_configs.constants import Capability
from eylo.modules.provider_configs.errors import NotConfiguredError

_CONFIGURE_VIA = "/api/llm-configs"


class LLMConfigResolver:
    """Resolve one explicitly selected, ready LLM config revision."""

    def __init__(self, configs: LLMConfigService):
        self._configs = configs

    async def resolve_llm(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID | None = None,
        overrides: LLMOverrides | Mapping[str, object] | None = None,
    ) -> ResolvedLLM:
        if provider_config_id is None:
            raise _not_configured("provider_config")

        selected = await self._configs.resolve_for_new_run(
            organization_id=organization_id,
            config_id=provider_config_id,
            granted=True,
        )
        try:
            provider_config = effective_to_llm_provider_config(selected)
        except InvalidLLMConfig:
            raise _not_configured("valid_provider_config") from None

        try:
            effective_overrides = (
                overrides
                if isinstance(overrides, LLMOverrides)
                else LLMOverrides.from_mapping(overrides)
            )
            return ResolvedLLM.from_provider_config(
                provider_config_id=selected.provider_config_id,
                provider_config_revision=selected.revision,
                organization_id=selected.organization_id,
                provider_config=provider_config,
                configured=selected.configured,
                verified=selected.verified,
                ready=selected.ready,
                granted=selected.granted,
                overrides=effective_overrides,
            )
        except InvalidLLMConfig:
            raise _not_configured("valid_overrides") from None

    async def resolve_llm_pinned(
        self,
        organization_id: UUID,
        *,
        provider_config_id: UUID,
        revision: int,
        overrides: LLMOverrides | Mapping[str, object] | None = None,
    ) -> ResolvedLLM:
        selected = await self._configs.resolve_pinned(
            organization_id=organization_id,
            config_id=provider_config_id,
            revision=revision,
            granted=True,
        )
        try:
            provider_config = effective_to_llm_provider_config(selected)
            effective_overrides = (
                overrides
                if isinstance(overrides, LLMOverrides)
                else LLMOverrides.from_mapping(overrides)
            )
            return ResolvedLLM.from_provider_config(
                provider_config_id=selected.provider_config_id,
                provider_config_revision=selected.revision,
                organization_id=selected.organization_id,
                provider_config=provider_config,
                configured=selected.configured,
                verified=selected.verified,
                ready=selected.ready,
                granted=selected.granted,
                overrides=effective_overrides,
            )
        except InvalidLLMConfig:
            raise _not_configured("valid_pinned_provider_config") from None


def _not_configured(missing: str) -> NotConfiguredError:
    return NotConfiguredError(
        capability=Capability.LLM,
        missing=[missing],
        configure_via=_CONFIGURE_VIA,
    )
