"""Credential encryption for the `provider_configs` domain."""

import base64
import binascii
import json
import os
import re
from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ENVELOPE_VERSION = "v1"
_KEY_HEX_LENGTH = 64
_KEY_BYTE_LENGTH = 32
_NONCE_LENGTH = 12
_CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class SecretCipherError(Exception):
    """Base error for provider-config encryption failures."""


class InvalidEncryptionKey(SecretCipherError):
    """Raised when ENCRYPTION_KEY does not satisfy the key contract."""


class InvalidEncryptionContext(SecretCipherError):
    """Raised when associated-data context is invalid."""


class SecretEncryptionError(SecretCipherError):
    """Raised when a secret mapping cannot be encrypted."""


class SecretDecryptionError(SecretCipherError):
    """Raised when a ciphertext envelope cannot be authenticated or decoded."""


@dataclass(frozen=True)
class EncryptionContext:
    organization_id: UUID
    config_id: UUID
    capability: str
    revision: int

    def associated_data(self) -> bytes:
        if not _CAPABILITY_PATTERN.fullmatch(self.capability):
            raise InvalidEncryptionContext(
                "Capability must be a lowercase machine-readable identifier."
            )
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 1
        ):
            raise InvalidEncryptionContext("Revision must be a positive integer.")
        return (
            "provider-config:"
            f"{self.organization_id}:{self.config_id}:{self.capability}:"
            f"{self.revision}"
        ).encode("utf-8")


def get_secret_cipher() -> "SecretCipher":
    """Build the provider secret cipher from validated application settings."""
    from eylo.common.config import settings

    return SecretCipher(settings.ENCRYPTION_KEY)


class SecretCipher:
    """Encrypt and decrypt provider secret mappings with a versioned envelope."""

    def __init__(self, key_hex: str):
        self._cipher = AESGCM(_decode_key(key_hex))

    def encrypt(
        self,
        secrets: Mapping[str, object],
        context: EncryptionContext,
    ) -> str:
        plaintext = _serialize_secrets(secrets)
        nonce = os.urandom(_NONCE_LENGTH)

        try:
            ciphertext = self._cipher.encrypt(
                nonce,
                plaintext,
                context.associated_data(),
            )
        except InvalidEncryptionContext:
            raise
        except (OverflowError, ValueError) as error:
            raise SecretEncryptionError("Secret payload encryption failed.") from error

        return ".".join(
            (
                _ENVELOPE_VERSION,
                _base64url_encode(nonce),
                _base64url_encode(ciphertext),
            )
        )

    def decrypt(
        self,
        envelope: str,
        context: EncryptionContext,
    ) -> dict[str, object]:
        nonce, ciphertext = _decode_envelope(envelope)

        try:
            plaintext = self._cipher.decrypt(
                nonce,
                ciphertext,
                context.associated_data(),
            )
            secrets = json.loads(plaintext.decode("utf-8"))
        except InvalidEncryptionContext:
            raise
        except (
            InvalidTag,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
        ) as error:
            raise SecretDecryptionError(
                "Secret payload could not be decrypted."
            ) from error

        if not isinstance(secrets, dict) or not all(
            isinstance(key, str) for key in secrets
        ):
            raise SecretDecryptionError(
                "Decrypted secret payload has an invalid shape."
            )

        return secrets

    def encrypt_field(self, value: str, context_label: str = "") -> str:
        """Encrypt a single string value and return a versioned envelope."""
        nonce = os.urandom(_NONCE_LENGTH)
        aad = context_label.encode("utf-8") if context_label else b""
        try:
            ciphertext = self._cipher.encrypt(nonce, value.encode("utf-8"), aad)
        except (OverflowError, ValueError) as error:
            raise SecretEncryptionError("Field encryption failed.") from error
        return ".".join(
            (_ENVELOPE_VERSION, _base64url_encode(nonce), _base64url_encode(ciphertext))
        )

    def decrypt_field(self, envelope: str, context_label: str = "") -> str:
        """Decrypt a single string value from a versioned envelope."""
        nonce, ciphertext = _decode_envelope(envelope)
        aad = context_label.encode("utf-8") if context_label else b""
        try:
            plaintext = self._cipher.decrypt(nonce, ciphertext, aad)
        except (InvalidTag, UnicodeDecodeError, ValueError) as error:
            raise SecretDecryptionError(
                "Field could not be decrypted."
            ) from error
        return plaintext.decode("utf-8")


def _decode_key(key_hex: str) -> bytes:
    if not isinstance(key_hex, str) or len(key_hex) != _KEY_HEX_LENGTH:
        raise InvalidEncryptionKey(
            "ENCRYPTION_KEY must be exactly 64 hexadecimal characters."
        )

    try:
        key = bytes.fromhex(key_hex)
    except ValueError as error:
        raise InvalidEncryptionKey(
            "ENCRYPTION_KEY must be exactly 64 hexadecimal characters."
        ) from error

    if len(key) != _KEY_BYTE_LENGTH:
        raise InvalidEncryptionKey("ENCRYPTION_KEY must decode to a 256-bit AES key.")
    return key


def _serialize_secrets(secrets: Mapping[str, object]) -> bytes:
    if not isinstance(secrets, Mapping) or not all(
        isinstance(key, str) for key in secrets
    ):
        raise SecretEncryptionError("Secret payload must be a string-keyed mapping.")

    try:
        return json.dumps(
            dict(secrets),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise SecretEncryptionError(
            "Secret payload must contain JSON-serializable values."
        ) from error


def _decode_envelope(envelope: str) -> tuple[bytes, bytes]:
    if not isinstance(envelope, str):
        raise SecretDecryptionError("Ciphertext envelope is malformed.")

    parts = envelope.split(".")
    if len(parts) != 3 or parts[0] != _ENVELOPE_VERSION:
        raise SecretDecryptionError("Ciphertext envelope version is unsupported.")

    try:
        nonce = _base64url_decode(parts[1])
        ciphertext = _base64url_decode(parts[2])
    except (binascii.Error, ValueError) as error:
        raise SecretDecryptionError("Ciphertext envelope is malformed.") from error

    if len(nonce) != _NONCE_LENGTH or len(ciphertext) < 16:
        raise SecretDecryptionError("Ciphertext envelope is malformed.")
    return nonce, ciphertext


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)
