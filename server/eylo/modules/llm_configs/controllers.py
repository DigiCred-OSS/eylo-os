"""Transport orchestration for the `llm_configs` domain."""

from collections.abc import Awaitable
from typing import TypeVar
from uuid import UUID

from fastapi import HTTPException, status

from eylo.modules.llm_configs.domain import InvalidLLMConfig
from eylo.modules.llm_configs.schemas import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigUpdate,
    LLMConfigVerificationResponse,
)
from eylo.modules.llm_configs.service import LLMConfigService
from eylo.modules.llm_configs.verification import (
    LLMConfigVerificationService,
    LLMVerificationError,
)
from eylo.modules.provider_configs.domain import (
    ProviderConfig,
)
from eylo.modules.provider_configs.masking import mask_secrets

_Result = TypeVar("_Result")


class LLMConfigController:
    """Translate authenticated LLM config requests and domain results."""

    def __init__(
        self,
        service: LLMConfigService,
        verification: LLMConfigVerificationService,
    ):
        self._service = service
        self._verification = verification

    async def create(
        self,
        organization_id: UUID,
        request: LLMConfigCreate,
    ) -> LLMConfigResponse:
        config = await _execute(
            self._service.create(
                organization_id=organization_id,
                provider=request.provider,
                name=request.name,
                config=request.config,
                secrets=request.secrets,
            )
        )
        return _to_response(config)

    async def list(self, organization_id: UUID) -> list[LLMConfigResponse]:
        configs = await _execute(self._service.list(organization_id=organization_id))
        return [_to_response(config) for config in configs]

    async def get(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> LLMConfigResponse:
        config = await _execute(
            self._service.get(
                organization_id=organization_id,
                config_id=config_id,
            )
        )
        return _to_response(config)

    async def update(
        self,
        organization_id: UUID,
        config_id: UUID,
        request: LLMConfigUpdate,
    ) -> LLMConfigResponse:
        supplied_fields = request.model_fields_set
        config = await _execute(
            self._service.update(
                organization_id=organization_id,
                config_id=config_id,
                name=request.name if "name" in supplied_fields else None,
                config_patch=(
                    request.config if "config" in supplied_fields else None
                ),
                secret_patch=(
                    request.secrets if "secrets" in supplied_fields else None
                ),
                enabled=request.enabled if "enabled" in supplied_fields else None,
            )
        )
        return _to_response(config)

    async def verify(
        self,
        organization_id: UUID,
        config_id: UUID,
    ) -> LLMConfigVerificationResponse:
        result = await _execute(
            self._verification.verify(
                organization_id=organization_id,
                config_id=config_id,
            )
        )
        return LLMConfigVerificationResponse(
            provider=result.provider,
            model=result.model,
            revision=result.revision,
            verified_at=result.verified_at,
        )

    async def delete(self, organization_id: UUID, config_id: UUID) -> None:
        await _execute(
            self._service.delete(
                organization_id=organization_id,
                config_id=config_id,
            )
        )


async def _execute(action: Awaitable[_Result]) -> _Result:
    try:
        return await action
    except InvalidLLMConfig as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except LLMVerificationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM provider verification failed.",
        ) from None


def _to_response(config: ProviderConfig) -> LLMConfigResponse:
    return LLMConfigResponse(
        id=config.id,
        provider=config.provider,
        name=config.name,
        revision=config.revision,
        enabled=config.enabled,
        configured=config.configured,
        verified=config.verified,
        ready=config.ready,
        verified_at=config.verified_at,
        config=dict(config.config),
        secrets=mask_secrets(config.secrets),
    )
