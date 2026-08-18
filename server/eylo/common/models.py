"""Shared SQLAlchemy model bases and tenant-scoping constraints."""

import uuid

import arrow
import uuid_utils
from slugify import slugify
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


def _uuid7() -> uuid.UUID:
    """Return the stdlib UUID type expected back from the PostgreSQL driver."""
    return uuid.UUID(str(uuid_utils.uuid7()))


def register_models():
    """Register all SQLAlchemy models from different modules.

    This function imports models from various Eylo modules to ensure
    they are registered with SQLAlchemy's declarative base.
    """
    # These imports are intentionally local and side-effectful. Alembic, workers,
    # and verifier scripts call this function without importing the HTTP routes.
    from eylo.events.durable import models as durable_event_models
    from eylo.modules.agent_runs import models as agent_run_models
    from eylo.modules.agents import models as agent_models
    from eylo.modules.auth import models as auth_models
    from eylo.modules.connections import models as connection_models
    from eylo.modules.contacts import models as contact_models
    from eylo.modules.conversations import models as conversation_models
    from eylo.modules.deletions import models as deletion_models
    from eylo.modules.integrations_v2 import models as integration_models
    from eylo.modules.knowledgebase import jobs as knowledge_job_models
    from eylo.modules.knowledgebase import models as knowledge_models
    from eylo.modules.mcp_servers import models as mcp_server_models
    from eylo.modules.members import models as member_models
    from eylo.modules.memory import models as memory_models
    from eylo.modules.organizations import models as organization_models
    from eylo.modules.provider_configs import models as provider_config_models
    from eylo.modules.sandbox import models as sandbox_models
    from eylo.modules.scheduler import models as scheduler_models
    from eylo.modules.telephony import models as telephony_models
    from eylo.modules.templates import models as template_models
    from eylo.modules.tools import models as tool_models
    from eylo.modules.user_sessions import models as user_session_models
    from eylo.modules.voice import models as voice_models
    from eylo.modules.voice_transcripts import models as voice_transcript_models
    from eylo.pipelines.outbound import models as outbound_models
    from eylo.products.campaigns import models as campaign_models

    _ = (
        durable_event_models,
        agent_run_models,
        agent_models,
        auth_models,
        connection_models,
        contact_models,
        conversation_models,
        deletion_models,
        integration_models,
        knowledge_job_models,
        knowledge_models,
        mcp_server_models,
        member_models,
        memory_models,
        organization_models,
        outbound_models,
        provider_config_models,
        sandbox_models,
        scheduler_models,
        telephony_models,
        template_models,
        tool_models,
        user_session_models,
        voice_models,
        voice_transcript_models,
        campaign_models,
    )


def server_now():
    """Get the current UTC time.

    Returns:
        datetime: Current UTC time as a datetime object.

    """
    return arrow.utcnow().datetime


def get_uuid_to_str():
    """Generate a new UUID and return it as a string.

    Returns:
        str: A new UUID as a string.

    """
    return str(uuid_utils.uuid7())


def slugify_column(value: str) -> str:
    """Convert a string to a slug format.

    Args:
        value (str): The string to be slugified.

    Returns:
        str: The slugified string.

    """
    return slugify(value, separator="_")


def validate_name_and_generate_slug(instance, key, name):
    """Validate a name and generate a slug for it."""
    if name:
        instance.slug = slugify_column(name)
    return name


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    pass


class EyloBaseModel(Base):
    """Base model for all Eylo entities."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=_uuid7, primary_key=True
    )

    deleted = mapped_column(Boolean, nullable=False, server_default="false")
    created_at = mapped_column(
        DateTime(
            timezone=True,
        ),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at = mapped_column(
        DateTime(
            timezone=True,
        ),
        server_default=func.now(),
        onupdate=server_now,
        nullable=False,
    )


class EyloOrganizationModel(EyloBaseModel):
    """Base model for all organization-related entities in Eylo."""

    __abstract__ = True

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=uuid_utils.uuid7,
    )

    external_id = mapped_column(
        String(320),
        default=get_uuid_to_str,
        unique=False,
    )

    @staticmethod
    def get_organization_constraints(tablename: str):
        """Return constraints that should be included in all organization models."""
        return [
            Index(
                f"ix_unq_{tablename}_ext_id_org_id",
                "external_id",
                "organization_id",
                unique=True,
            )
        ]
