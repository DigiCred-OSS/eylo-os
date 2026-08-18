"""One organization-scoped application port for template lifecycle and render."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from eylo.common.database import get_transaction
from eylo.common.models import slugify_column
from eylo.common.revisions import (
    DefinitionHeaderState,
    DefinitionLifecycle,
    DefinitionRef,
    PublishedRevisionState,
)
from eylo.modules.templates.domain import (
    RENDERER_VERSION,
    InvalidTemplateError,
    RenderedTemplate,
    TemplateConflictError,
    TemplateConsumerKind,
    TemplateKind,
    TemplateNotFoundError,
    compile_template,
    render_template,
)
from eylo.modules.templates.models import TemplateModel, TemplateRevisionModel


class _TemplateRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_header(
        self,
        organization_id: UUID,
        template_id: UUID,
        *,
        for_update: bool = False,
    ) -> TemplateModel:
        query = select(TemplateModel).where(
            TemplateModel.id == template_id,
            TemplateModel.organization_id == organization_id,
            TemplateModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        template = await self._db.scalar(query)
        if template is None:
            raise TemplateNotFoundError("Template not found.")
        return template

    async def get_revision(
        self,
        organization_id: UUID,
        template_id: UUID,
        revision: int,
        *,
        for_update: bool = False,
    ) -> TemplateRevisionModel:
        query = select(TemplateRevisionModel).where(
            TemplateRevisionModel.template_id == template_id,
            TemplateRevisionModel.organization_id == organization_id,
            TemplateRevisionModel.revision == revision,
            TemplateRevisionModel.deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        row = await self._db.scalar(query)
        if row is None:
            raise TemplateNotFoundError("Template revision not found.")
        return row

    async def list_headers(self, organization_id: UUID) -> list[TemplateModel]:
        rows = await self._db.scalars(
            select(TemplateModel)
            .where(
                TemplateModel.organization_id == organization_id,
                TemplateModel.deleted.is_(False),
            )
            .order_by(TemplateModel.created_at.desc())
        )
        return list(rows.all())

    async def slug_exists(self, organization_id: UUID, slug: str) -> bool:
        return (
            await self._db.scalar(
                select(TemplateModel.id).where(
                    TemplateModel.organization_id == organization_id,
                    TemplateModel.slug == slug,
                    TemplateModel.deleted.is_(False),
                )
            )
            is not None
        )


class TemplateService:
    """Complete draft/publish/load/render authority for templates."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._db = db or get_transaction()
        self._repository = _TemplateRepository(self._db)

    async def create(
        self,
        *,
        organization_id: UUID,
        name: str,
        kind: TemplateKind | str,
        body: str,
        variable_schema: dict[str, object],
    ) -> TemplateModel:
        name = _name(name)
        kind = TemplateKind(kind)
        compiled = compile_template(body, variable_schema)
        slug = slugify_column(name)
        if not slug or await self._repository.slug_exists(organization_id, slug):
            raise TemplateConflictError("Template name is already in use.")
        row = TemplateModel(
            organization_id=organization_id,
            name=name,
            slug=slug,
            kind=kind.value,
            draft_body=compiled.body,
            draft_variable_schema=compiled.to_storage(),
        )
        self._db.add(row)
        try:
            await self._db.flush()
        except IntegrityError as error:
            raise TemplateConflictError("Template name is already in use.") from error
        return row

    async def get(
        self,
        *,
        organization_id: UUID,
        template_id: UUID,
    ) -> TemplateModel:
        return await self._repository.get_header(organization_id, template_id)

    async def list(self, *, organization_id: UUID) -> list[TemplateModel]:
        return await self._repository.list_headers(organization_id)

    async def update_draft(
        self,
        *,
        organization_id: UUID,
        template_id: UUID,
        expected_draft_version: int,
        body: str | None = None,
        variable_schema: dict[str, object] | None = None,
    ) -> TemplateModel:
        row = await self._repository.get_header(
            organization_id,
            template_id,
            for_update=True,
        )
        state = _header_state(row).edit(
            expected_draft_version=expected_draft_version
        )
        compiled = compile_template(
            row.draft_body if body is None else body,
            (
                row.draft_variable_schema
                if variable_schema is None
                else variable_schema
            ),
        )
        row.draft_body = compiled.body
        row.draft_variable_schema = compiled.to_storage()
        _apply_header_state(row, state)
        await self._db.flush()
        return row

    async def publish(
        self,
        *,
        organization_id: UUID,
        template_id: UUID,
        expected_draft_version: int,
    ) -> TemplateRevisionModel:
        row = await self._repository.get_header(
            organization_id,
            template_id,
            for_update=True,
        )
        compiled = compile_template(row.draft_body, row.draft_variable_schema)
        next_revision = (row.published_revision or 0) + 1
        state = _header_state(row).publish(
            revision=next_revision,
            expected_draft_version=expected_draft_version,
        )
        published_at = datetime.now(timezone.utc)
        revision = TemplateRevisionModel(
            organization_id=organization_id,
            template_id=row.id,
            revision=next_revision,
            kind=TemplateKind(row.kind).value,
            body=compiled.body,
            variable_schema=compiled.to_storage(),
            renderer_version=RENDERER_VERSION,
            published_at=published_at,
        )
        self._db.add(revision)
        await self._db.flush()
        _apply_header_state(row, state)
        await self._db.flush()
        return revision

    async def get_revision(
        self,
        *,
        organization_id: UUID,
        template_id: UUID,
        revision: int,
        for_update: bool = False,
    ) -> TemplateRevisionModel:
        return await self._repository.get_revision(
            organization_id,
            template_id,
            revision,
            for_update=for_update,
        )

    async def resolve_for_new_work(
        self,
        *,
        organization_id: UUID,
        template_id: UUID,
        for_update: bool = False,
    ) -> TemplateRevisionModel:
        header = await self._repository.get_header(
            organization_id,
            template_id,
            for_update=for_update,
        )
        revision_number = _header_state(header).revision_for_new_work()
        revision = await self._repository.get_revision(
            organization_id,
            template_id,
            revision_number,
            for_update=for_update,
        )
        _revision_state(revision).require_available()
        return revision

    async def preview(
        self,
        *,
        organization_id: UUID,
        template_id: UUID,
        consumer_kind: TemplateConsumerKind | str,
        values: dict[str, object],
    ) -> RenderedTemplate:
        row = await self._repository.get_header(organization_id, template_id)
        compiled = compile_template(row.draft_body, row.draft_variable_schema)
        rendered = render_template(
            compiled,
            kind=TemplateKind(row.kind),
            consumer_kind=consumer_kind,
            values=values,
        )
        return replace(
            rendered,
            template_id=row.id,
            draft_version=row.draft_version,
        )

    async def render_exact(
        self,
        *,
        organization_id: UUID,
        template_id: UUID,
        revision: int,
        consumer_kind: TemplateConsumerKind | str,
        values: dict[str, object],
    ) -> RenderedTemplate:
        row = await self._repository.get_revision(
            organization_id,
            template_id,
            revision,
        )
        _revision_state(row).require_available()
        compiled = compile_template(row.body, row.variable_schema)
        rendered = render_template(
            compiled,
            kind=TemplateKind(row.kind),
            consumer_kind=consumer_kind,
            values=values,
        )
        return replace(
            rendered,
            template_ref=DefinitionRef(
                definition_id=template_id,
                revision=revision,
            ),
            template_id=template_id,
        )

    async def withdraw(
        self,
        *,
        organization_id: UUID,
        template_id: UUID,
    ) -> TemplateModel:
        row = await self._repository.get_header(
            organization_id,
            template_id,
            for_update=True,
        )
        _apply_header_state(row, _header_state(row).withdraw())
        await self._db.flush()
        return row

    async def revoke(
        self,
        *,
        organization_id: UUID,
        template_id: UUID,
        revision: int,
        actor_id: UUID,
        reason: str,
    ) -> TemplateRevisionModel:
        header = await self._repository.get_header(
            organization_id,
            template_id,
            for_update=True,
        )
        row = await self._repository.get_revision(
            organization_id,
            template_id,
            revision,
            for_update=True,
        )
        revoked = _revision_state(row).revoke(
            actor_id=actor_id,
            reason=reason,
            at=datetime.now(timezone.utc),
        )
        row.availability = revoked.availability.value
        row.revoked_at = revoked.revoked_at
        row.revoked_by = revoked.revoked_by
        row.revocation_reason = revoked.revocation_reason
        row.cancellation_requested_at = revoked.cancellation_requested_at
        if header.published_revision == revision:
            _apply_header_state(header, _header_state(header).withdraw())
        await self._db.flush()
        return row


def _header_state(row: TemplateModel) -> DefinitionHeaderState:
    return DefinitionHeaderState(
        lifecycle=DefinitionLifecycle(row.lifecycle),
        published_revision=row.published_revision,
        draft_version=row.draft_version,
        draft_dirty=row.draft_dirty,
    )


def _apply_header_state(
    row: TemplateModel,
    state: DefinitionHeaderState,
) -> None:
    row.lifecycle = state.lifecycle.value
    row.published_revision = state.published_revision
    row.draft_version = state.draft_version
    row.draft_dirty = state.draft_dirty


def _revision_state(row: TemplateRevisionModel) -> PublishedRevisionState:
    return PublishedRevisionState(
        published_at=row.published_at,
        availability=row.availability,
        revoked_at=row.revoked_at,
        revoked_by=row.revoked_by,
        revocation_reason=row.revocation_reason,
        cancellation_requested_at=row.cancellation_requested_at,
    )


def _name(value: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized or len(normalized) > 128:
        raise InvalidTemplateError("Template name must contain 1 to 128 characters.")
    return normalized


__all__ = ["TemplateService"]
