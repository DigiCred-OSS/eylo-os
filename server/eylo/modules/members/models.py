"""Database models for platform users."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from eylo.common.models import EyloOrganizationModel

from .constants import APP_DB_PREFIX


class MemberStatus(str, Enum):
    """Enum for org member status"""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    WAITLIST = "WAITLIST"


class MemberModel(EyloOrganizationModel):
    __tablename__ = f"{APP_DB_PREFIX}members"

    __table_args__ = (
        *EyloOrganizationModel.get_organization_constraints(__tablename__),
    )

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MemberStatus] = mapped_column(
        String(32), nullable=False, default=MemberStatus.ACTIVE
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
