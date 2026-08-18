"""Strict runtime configs passed into storage vendor adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from eylo.sockets.storage.base import StorageOperationError, validate_key


class S3StorageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    vendor: Literal["s3"] = "s3"
    bucket: str = Field(min_length=3, max_length=63)
    region: str = Field(min_length=5, max_length=64)
    key_prefix: str = Field(min_length=1, max_length=512)
    access_key_id: SecretStr
    secret_access_key: SecretStr
    session_token: SecretStr | None = None

    @field_validator("key_prefix")
    @classmethod
    def validate_key_prefix(cls, value: str) -> str:
        try:
            return validate_key(value)
        except StorageOperationError as error:
            raise ValueError("S3 key prefix must be a relative object key.") from error


class FilesystemStorageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vendor: Literal["filesystem"] = "filesystem"
    root: Path

    @model_validator(mode="after")
    def validate_root(self) -> Self:
        if not self.root.is_absolute() or self.root == Path(self.root.anchor):
            raise ValueError("Filesystem storage root must be a scoped absolute path.")
        return self


StorageConfig = Annotated[
    S3StorageConfig | FilesystemStorageConfig,
    Field(discriminator="vendor"),
]
