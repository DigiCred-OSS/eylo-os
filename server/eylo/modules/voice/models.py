"""Organization-owned Voice Config persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloOrganizationModel

# Registration import: recordings belong to the voice module but use a
# separate persistence file.
from eylo.modules.voice.recording.model import VoiceRecordingModel  # noqa: F401


class VoiceConfigModel(EyloOrganizationModel):
    """Reusable current Voice Config definition owned by one organization.

    Published agent revisions retain immutable runtime snapshots, so this row
    only needs the current editable definition and its monotonic revision.
    Provider revisions are deliberately absent: they are resolved when an
    agent is published and pinned on that agent revision.
    """

    __tablename__ = "voice_configs"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_voice_configs_id_organization_id",
        ),
        Index(
            "uq_voice_configs_name_organization_active",
            "organization_id",
            "name",
            unique=True,
            postgresql_where=text("deleted = false"),
        ),
        CheckConstraint(
            "revision > 0",
            name="ck_voice_configs_revision_positive",
        ),
        *(
            ForeignKeyConstraint(
                [f"{kind}_provider_config_id", "organization_id"],
                ["provider_configs.id", "provider_configs.organization_id"],
                name=f"fk_voice_configs_{kind}_config_organization",
                ondelete="RESTRICT",
            )
            for kind in ("stt", "tts", "realtime", "storage")
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    stt_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    tts_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    realtime_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    storage_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    definition: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        doc="VoiceConfig fields excluding provider ids and resolved revisions.",
    )
