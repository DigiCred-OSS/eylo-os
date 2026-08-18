"""Strict API contracts for template draft, publication, and rendering."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from eylo.common.revisions import DefinitionLifecycle, RevisionAvailability
from eylo.modules.templates.domain import (
    MAX_TEMPLATE_BODY_CHARS,
    MAX_VARIABLES,
    RenderedTemplate,
    TemplateConsumerKind,
    TemplateKind,
    TemplateSegmentAuthority,
    TemplateVariableType,
)


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TemplateVariableSchema(StrictSchema):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    type: TemplateVariableType


class TemplateVariablesSchema(StrictSchema):
    variables: list[TemplateVariableSchema] = Field(max_length=MAX_VARIABLES)

    @model_validator(mode="after")
    def unique_names(self) -> TemplateVariablesSchema:
        names = [variable.name for variable in self.variables]
        if len(names) != len(set(names)):
            raise ValueError("Template variable names must be unique.")
        return self

    def to_storage(self) -> dict[str, list[dict[str, str]]]:
        return {
            "variables": [
                {"name": variable.name, "type": variable.type.value}
                for variable in self.variables
            ]
        }


class TemplateCreateRequest(StrictSchema):
    name: str = Field(min_length=1, max_length=128)
    kind: TemplateKind
    body: str = Field(min_length=1, max_length=MAX_TEMPLATE_BODY_CHARS)
    variable_schema: TemplateVariablesSchema


class TemplateDraftUpdateRequest(StrictSchema):
    expected_draft_version: int = Field(gt=0)
    body: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_TEMPLATE_BODY_CHARS,
    )
    variable_schema: TemplateVariablesSchema | None = None

    @model_validator(mode="after")
    def require_change(self) -> TemplateDraftUpdateRequest:
        if self.body is None and self.variable_schema is None:
            raise ValueError("A draft update requires body or variable_schema.")
        return self


class TemplatePublishRequest(StrictSchema):
    expected_draft_version: int = Field(gt=0)


class TemplatePreviewRequest(StrictSchema):
    consumer_kind: TemplateConsumerKind
    variables: dict[str, Any]


class TemplateRenderRequest(StrictSchema):
    consumer_kind: TemplateConsumerKind
    variables: dict[str, Any]


class TemplateRevokeRequest(StrictSchema):
    reason: str = Field(min_length=1, max_length=2_000)


class TemplateResponse(StrictSchema):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    kind: TemplateKind
    lifecycle: DefinitionLifecycle
    published_revision: int | None
    draft_version: int
    draft_dirty: bool
    draft_body: str
    draft_variable_schema: TemplateVariablesSchema
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "organization_id", mode="before")
    @classmethod
    def normalize_uuid(cls, value: object) -> UUID:
        return value if isinstance(value, UUID) else UUID(str(value))


class TemplateRevisionResponse(StrictSchema):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    template_id: UUID
    organization_id: UUID
    revision: int
    kind: TemplateKind
    body: str
    variable_schema: TemplateVariablesSchema
    renderer_version: str
    availability: RevisionAvailability
    published_at: datetime
    revoked_at: datetime | None
    revoked_by: UUID | None
    revocation_reason: str | None
    cancellation_requested_at: datetime | None

    @field_validator(
        "template_id",
        "organization_id",
        "revoked_by",
        mode="before",
    )
    @classmethod
    def normalize_uuid(cls, value: object | None) -> UUID | None:
        if value is None or isinstance(value, UUID):
            return value
        return UUID(str(value))


class TemplateSegmentResponse(StrictSchema):
    authority: TemplateSegmentAuthority
    text: str
    variable_name: str | None


class TemplateRenderResponse(StrictSchema):
    template_id: UUID
    revision: int | None = None
    draft_version: int | None = None
    renderer_version: str
    consumer_kind: TemplateConsumerKind
    variable_names: list[str]
    text: str
    segments: list[TemplateSegmentResponse]

    @model_validator(mode="after")
    def one_source_revision(self) -> TemplateRenderResponse:
        if (self.revision is None) == (self.draft_version is None):
            raise ValueError(
                "A render response requires exactly one revision or draft_version."
            )
        return self

    @classmethod
    def from_domain(
        cls,
        rendered: RenderedTemplate,
        *,
        template_id: UUID,
        revision: int | None = None,
        draft_version: int | None = None,
    ) -> TemplateRenderResponse:
        return cls(
            template_id=template_id,
            revision=revision,
            draft_version=draft_version,
            renderer_version=rendered.renderer_version,
            consumer_kind=rendered.consumer_kind,
            variable_names=list(rendered.variable_names),
            text=rendered.text,
            segments=[
                TemplateSegmentResponse(
                    authority=segment.authority,
                    text=segment.text,
                    variable_name=segment.variable_name,
                )
                for segment in rendered.segments
            ],
        )


__all__ = [
    "TemplateCreateRequest",
    "TemplateDraftUpdateRequest",
    "TemplatePreviewRequest",
    "TemplatePublishRequest",
    "TemplateRenderRequest",
    "TemplateRenderResponse",
    "TemplateResponse",
    "TemplateRevisionResponse",
    "TemplateRevokeRequest",
    "TemplateVariableSchema",
    "TemplateVariablesSchema",
]
