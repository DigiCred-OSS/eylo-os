"""Translate provider-configuration failures into safe HTTP responses."""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

from eylo.common.contracts.provider_config import ProviderConfigError
from eylo.modules.provider_configs.crypto import SecretCipherError
from eylo.modules.provider_configs.domain import (
    InvalidProviderConfig,
    ProviderConfigConflict,
    ProviderConfigNotFound,
)
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.provider_configs.masking import (
    InvalidSecretPatch,
    InvalidSecretPayload,
)

logger = logging.getLogger(__name__)


async def handle_not_configured(
    _request: Request,
    error: NotConfiguredError,
) -> JSONResponse:
    """Map missing capability details to the stable HTTP 409 contract."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "capability": error.capability.value,
            "missing": list(error.missing),
            "configure_via": error.configure_via,
        },
    )


async def handle_provider_config_error(
    _request: Request,
    error: ProviderConfigError,
) -> JSONResponse:
    """Map shared lifecycle failures identically across capability routes."""
    if isinstance(error, ProviderConfigNotFound):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "provider_config_not_found",
                "detail": "Provider configuration was not found.",
            },
        )
    if isinstance(error, ProviderConfigConflict):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "provider_config_conflict",
                "detail": str(error),
            },
        )
    if isinstance(
        error,
        (InvalidProviderConfig, InvalidSecretPatch, InvalidSecretPayload),
    ):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "invalid_provider_config",
                "detail": str(error),
            },
        )
    logger.error("Unhandled provider-config error type: %s", type(error).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "provider_config_error",
            "detail": "Provider configuration could not be processed.",
        },
    )


async def handle_secret_cipher_error(
    _request: Request,
    error: SecretCipherError,
) -> JSONResponse:
    """Map an encryption failure to a stable HTTP 503 contract.

    Without this, a stored secret that cannot be decrypted — a rotated or
    corrupted `ENCRYPTION_KEY`, a damaged envelope — surfaces as an
    unhandled 500 with a stack trace, or as an unanswered WebSocket event.

    The response body deliberately carries no detail. Ciphertext, key
    material, and the underlying message are logged server-side only: an
    operator needs them, a caller must never receive them.
    """
    logger.error(
        "Provider-config secret could not be processed error_type=%s",
        type(error).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "secret_unavailable",
            "detail": (
                "A stored credential could not be decrypted. This usually "
                "means ENCRYPTION_KEY changed or the stored value is "
                "corrupt. Check server logs and re-save the affected "
                "provider configuration."
            ),
        },
    )
