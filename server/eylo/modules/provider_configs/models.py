"""Persistence models for the `provider_configs` domain."""

import re
from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, validates

from eylo.common.models import EyloOrganizationModel
from eylo.modules.provider_configs.constants import Capability

_CAPABILITY_ENUM_NAME = "provider_capability_enum"
_PROVIDER_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class ProviderConfigValidationError(Exception):
    """Raised when a provider configuration violates a model invariant."""


class ProviderConfigModel(EyloOrganizationModel):
    """Organization-scoped external capability configuration."""

    __tablename__ = "provider_configs"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_provider_configs_id_organization_id",
        ),
        Index(
            "uq_provider_configs_org_capability_name_active",
            "organization_id",
            "capability",
            "name",
            unique=True,
            postgresql_where=text("deleted = false"),
        ),
    )

    capability: Mapped[Capability] = mapped_column(
        ENUM(
            Capability,
            name=_CAPABILITY_ENUM_NAME,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    encrypted_secrets: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    @validates("capability")
    def validate_capability(self, _key: str, value: Capability | str) -> Capability:
        try:
            return Capability(value)
        except ValueError as error:
            raise ProviderConfigValidationError(
                "Capability is not supported."
            ) from error

    @validates("provider")
    def normalize_provider(self, _key: str, value: str) -> str:
        normalized = value.strip().lower() if isinstance(value, str) else ""
        if not _PROVIDER_PATTERN.fullmatch(normalized):
            raise ProviderConfigValidationError(
                "Provider must be a lowercase machine-readable identifier."
            )
        return normalized

    @validates("name")
    def normalize_name(self, _key: str, value: str) -> str:
        normalized = value.strip() if isinstance(value, str) else ""
        if not normalized:
            raise ProviderConfigValidationError("Name cannot be empty.")
        return normalized

    @validates("config")
    def validate_config(self, _key: str, value: dict) -> dict:
        if not isinstance(value, Mapping) or not all(
            isinstance(key, str) for key in value
        ):
            raise ProviderConfigValidationError(
                "Config must be a string-keyed mapping."
            )
        return dict(value)

    @validates("encrypted_secrets")
    def validate_encrypted_secrets(self, _key: str, value: str) -> str:
        if not isinstance(value, str) or not value:
            raise ProviderConfigValidationError("Encrypted secrets cannot be empty.")
        return value

    @validates("revision")
    def validate_revision(self, _key: str, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ProviderConfigValidationError(
                "Revision must be a positive integer."
            )
        return value


class ProviderConfigRevisionModel(EyloOrganizationModel):
    """Immutable settings, secrets and verification for one config revision."""

    __tablename__ = "provider_config_revisions"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        ForeignKeyConstraint(
            ["provider_config_id", "organization_id"],
            ["provider_configs.id", "provider_configs.organization_id"],
            name="fk_provider_config_revisions_config_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "provider_config_id",
            "revision",
            name="uq_provider_config_revisions_config_revision",
        ),
        UniqueConstraint(
            "provider_config_id",
            "revision",
            "organization_id",
            name="uq_provider_config_revisions_config_revision_organization",
        ),
    )

    provider_config_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    encrypted_secrets: Mapped[str] = mapped_column(Text, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    verification_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    @validates("revision")
    def validate_revision(self, _key: str, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ProviderConfigValidationError(
                "Revision must be a positive integer."
            )
        return value

    @validates("config")
    def validate_config(self, _key: str, value: dict) -> dict:
        if not isinstance(value, Mapping) or not all(
            isinstance(key, str) for key in value
        ):
            raise ProviderConfigValidationError(
                "Config must be a string-keyed mapping."
            )
        return dict(value)

    @validates("encrypted_secrets")
    def validate_encrypted_secrets(self, _key: str, value: str) -> str:
        if not isinstance(value, str) or not value:
            raise ProviderConfigValidationError("Encrypted secrets cannot be empty.")
        return value

    @validates("verification_metadata")
    def validate_verification_metadata(self, _key: str, value: dict) -> dict:
        if not isinstance(value, Mapping) or not all(
            isinstance(key, str) for key in value
        ):
            raise ProviderConfigValidationError(
                "Verification metadata must be a string-keyed mapping."
            )
        return dict(value)
