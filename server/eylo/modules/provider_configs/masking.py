"""Secret-safe configuration projection for the `provider_configs` domain."""

from collections.abc import Mapping

from eylo.common.contracts.provider_config import ProviderConfigError

MASKED_SECRET_VALUE = "••••••••"


class InvalidSecretPayload(ProviderConfigError):
    """Raised when stored secret data violates the foundation contract."""


class InvalidSecretPatch(ProviderConfigError):
    """Raised when a secret patch could persist an invalid value."""


def mask_secrets(secrets: Mapping[str, str]) -> dict[str, str]:
    """Return configured secret keys without exposing their values."""
    _validate_secret_mapping(secrets)
    return {key: MASKED_SECRET_VALUE for key in sorted(secrets)}


def apply_secret_patch(
    stored_secrets: Mapping[str, str],
    patch: Mapping[str, str | None],
) -> dict[str, str]:
    """Apply omitted/present/null PATCH semantics without mutating inputs."""
    _validate_secret_mapping(stored_secrets)
    if not isinstance(patch, Mapping) or not all(isinstance(key, str) for key in patch):
        raise InvalidSecretPatch("Secret patch must be a string-keyed mapping.")

    updated = dict(stored_secrets)
    for key, value in patch.items():
        if value is None:
            updated.pop(key, None)
            continue
        if not isinstance(value, str):
            raise InvalidSecretPatch("Secret values must be strings or null.")
        if value == MASKED_SECRET_VALUE:
            raise InvalidSecretPatch("Masked secret values cannot be submitted.")
        if value == "":
            raise InvalidSecretPatch("Secret values cannot be empty strings.")
        updated[key] = value

    return updated


def _validate_secret_mapping(secrets: Mapping[str, str]) -> None:
    if not isinstance(secrets, Mapping) or not all(
        isinstance(key, str) for key in secrets
    ):
        raise InvalidSecretPayload("Secrets must be a string-keyed mapping.")
    if not all(isinstance(value, str) and value != "" for value in secrets.values()):
        raise InvalidSecretPayload("Stored secret values must be non-empty strings.")
