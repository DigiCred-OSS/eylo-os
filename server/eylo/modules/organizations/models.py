"""Persistence models for the `organizations` domain."""

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Text

from eylo.common.models import EyloBaseModel


class OrganizationModel(EyloBaseModel):
    """OrganizationModel behavior for the "organizations" domain."""

    __tablename__ = "organization_organizations"

    name: Mapped[str] = mapped_column(Text, nullable=False)
