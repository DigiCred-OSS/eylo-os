"""Conversation-scoped Knowledge routes for authenticated widget contacts."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import PurePath
from urllib.parse import unquote
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status

from eylo.common.contracts.knowledgebase import KnowledgeDocument, KnowledgeScope
from eylo.common.database import get_transaction, start_transaction
from eylo.common.revisions import DefinitionRevisionError
from eylo.modules.agents.exceptions import AgentNotFoundError
from eylo.modules.auth.dependencies.widget_auth import get_current_contact
from eylo.modules.auth.schemas import CurrentContactSchema
from eylo.modules.conversations.exceptions import ConversationNotFound
from eylo.modules.conversations.services.conversations import ConversationBaseService
from eylo.modules.knowledgebase.extraction import (
    DocumentExtractionError,
    extract_text,
    is_supported,
)
from eylo.modules.knowledgebase.jobs import MAX_STORAGE_OBJECT_BYTES
from eylo.modules.knowledgebase.schemas import (
    WidgetKnowledgeIngestionRead,
    WidgetKnowledgeUploadCapabilityRead,
)
from eylo.modules.knowledgebase.services.ingestion import (
    IngestionError,
    IngestionService,
)
from eylo.modules.knowledgebase.services.knowledgebases import (
    KnowledgebaseError,
    KnowledgebaseService,
)
from eylo.modules.user_sessions.domain import UserSessionError
from eylo.modules.user_sessions.events import file_user_session_fact
from eylo.modules.user_sessions.service import UserSessionService
from eylo.pipelines.knowledgebase.conversation_files import (
    ConversationFileUploadsNotAllowed,
    ensure_conversation_file_knowledgebase,
    resolve_conversation_file_upload_authority,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=(
        "/widget/{organization_id}/conversations/{conversation_id}/knowledgebases"
    ),
    tags=["Widget"],
)


def _authorize_context(
    organization_id: UUID,
    conversation_id: UUID,
    current_contact: CurrentContactSchema,
) -> None:
    if (
        str(organization_id) != str(current_contact.organization_id)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


async def _file_upload_authority(
    current_contact: CurrentContactSchema,
    conversation_id: UUID,
):
    return await resolve_conversation_file_upload_authority(
        organization_id=current_contact.organization_id,
        contact_id=current_contact.contact_id,
        conversation_id=conversation_id,
        session=get_transaction(),
    )


async def _authorize_user_session(
    *,
    organization_id: UUID,
    contact_id: UUID,
    conversation_id: UUID,
    user_session_id: UUID,
) -> None:
    try:
        await UserSessionService(get_transaction()).require_conversation_link(
            organization_id=organization_id,
            contact_id=contact_id,
            user_session_id=user_session_id,
            conversation_id=conversation_id,
        )
    except UserSessionError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error


@router.get(
    "/file-upload-capability",
    response_model=WidgetKnowledgeUploadCapabilityRead,
)
async def get_widget_knowledge_file_upload_capability(
    organization_id: UUID,
    conversation_id: UUID,
    user_session_id: UUID = Header(alias="X-Eylo-User-Session-ID"),
    current_contact: CurrentContactSchema = Depends(get_current_contact),
):
    """Tell the widget whether the exact pinned Agent revision permits files."""
    _authorize_context(organization_id, conversation_id, current_contact)
    async with start_transaction(ro=True):
        try:
            await _authorize_user_session(
                organization_id=organization_id,
                contact_id=current_contact.contact_id,
                conversation_id=conversation_id,
                user_session_id=user_session_id,
            )
            await _file_upload_authority(current_contact, conversation_id)
        except ConversationFileUploadsNotAllowed:
            return WidgetKnowledgeUploadCapabilityRead(allowed=False)
        except (
            AgentNotFoundError,
            ConversationNotFound,
            DefinitionRevisionError,
        ) as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    return WidgetKnowledgeUploadCapabilityRead(allowed=True)


@router.post(
    "/files",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=WidgetKnowledgeIngestionRead,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def upload_widget_knowledge_file(
    organization_id: UUID,
    conversation_id: UUID,
    request: Request,
    encoded_filename: str = Header(alias="X-Eylo-Filename"),
    user_session_id: UUID = Header(alias="X-Eylo-User-Session-ID"),
    current_contact: CurrentContactSchema = Depends(get_current_contact),
):
    """Extract one bounded file and enqueue ordinary durable ingestion."""
    _authorize_context(organization_id, conversation_id, current_contact)

    # Refuse a disabled capability before reading or parsing attacker-controlled
    # bytes. The write transaction repeats the immutable revision lookup.
    async with start_transaction(ro=True):
        try:
            await _authorize_user_session(
                organization_id=organization_id,
                contact_id=current_contact.contact_id,
                conversation_id=conversation_id,
                user_session_id=user_session_id,
            )
            await _file_upload_authority(current_contact, conversation_id)
        except (
            AgentNotFoundError,
            ConversationNotFound,
            ConversationFileUploadsNotAllowed,
            DefinitionRevisionError,
        ) as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error

    filename = _decode_filename(encoded_filename)
    if not is_supported(filename):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported Knowledge file type.",
        )
    raw = await _read_bounded_file(request)
    content_type = (request.headers.get("content-type") or "")[:255]

    try:
        content = await asyncio.to_thread(extract_text, filename, raw)
    except DocumentExtractionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    digest = hashlib.sha256(raw).hexdigest()
    source_uri = (
        f"eylo://conversations/{conversation_id}/uploads/{digest}"
    )

    async with start_transaction() as db_session:
        try:
            await _authorize_user_session(
                organization_id=organization_id,
                contact_id=current_contact.contact_id,
                conversation_id=conversation_id,
                user_session_id=user_session_id,
            )
            authority = await _file_upload_authority(current_contact, conversation_id)
            knowledgebase = await ensure_conversation_file_knowledgebase(
                authority,
                session=get_transaction(),
            )
        except (
            AgentNotFoundError,
            ConversationNotFound,
            ConversationFileUploadsNotAllowed,
            DefinitionRevisionError,
        ) as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        except KnowledgebaseError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Conversation file uploads are currently unavailable.",
            ) from error
        document = KnowledgeDocument(
            content=content,
            scope=KnowledgeScope.CONVERSATION,
            scope_id=str(conversation_id),
            title=filename,
            source_uri=source_uri,
            metadata={
                "source_kind": "conversation_upload",
                "filename": filename,
                "content_type": content_type,
                "byte_size": len(raw),
                "sha256": digest,
                "uploaded_by_contact_id": str(current_contact.contact_id),
            },
        )
        try:
            job = await IngestionService(get_transaction()).enqueue(
                organization_id=current_contact.organization_id,
                knowledgebase_id=knowledgebase.id,
                document=document,
                user_session_id=user_session_id,
            )
        except IngestionError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        response = _widget_ingestion_read(job)
        await file_user_session_fact(
            db_session,
            organization_id=organization_id,
            user_session_id=user_session_id,
            subject_type="knowledge.ingestion",
            subject_id=job.id,
            event_type="knowledge.file.accepted",
            payload={
                "conversation_id": str(conversation_id),
                "knowledgebase_id": str(knowledgebase.id),
                "document_id": str(job.document_id),
                "byte_size": len(raw),
            },
        )
        if str(job.user_session_id) == str(user_session_id):
            await file_user_session_fact(
                db_session,
                organization_id=organization_id,
                user_session_id=user_session_id,
                subject_type="knowledge.ingestion",
                subject_id=job.id,
                event_type="knowledge.ingestion.queued",
                event_id=uuid5(
                    NAMESPACE_URL,
                    f"eylo:knowledge.ingestion.queued:v1:{organization_id}:{job.id}",
                ),
                payload={
                    "conversation_id": str(conversation_id),
                    "knowledgebase_id": str(knowledgebase.id),
                    "document_id": str(job.document_id),
                },
            )

    from eylo.pipelines.knowledgebase.durable_execution import (
        spawn_knowledge_ingestion,
    )

    try:
        await spawn_knowledge_ingestion(
            organization_id=current_contact.organization_id,
            job_id=response.id,
        )
    except Exception as error:  # noqa: BLE001 - committed DB outbox is durable
        logger.error(
            "Could not immediately spawn conversation upload id=%s error_type=%s",
            response.id,
            type(error).__name__,
        )
    return response


@router.get(
    "/ingestions/{job_id}",
    response_model=WidgetKnowledgeIngestionRead,
)
async def get_widget_knowledge_ingestion(
    organization_id: UUID,
    conversation_id: UUID,
    job_id: UUID,
    user_session_id: UUID = Header(alias="X-Eylo-User-Session-ID"),
    current_contact: CurrentContactSchema = Depends(get_current_contact),
):
    """Return the durable state of one upload accepted in this conversation."""
    _authorize_context(organization_id, conversation_id, current_contact)
    async with start_transaction(ro=True):
        try:
            await _authorize_user_session(
                organization_id=organization_id,
                contact_id=current_contact.contact_id,
                conversation_id=conversation_id,
                user_session_id=user_session_id,
            )
            await ConversationBaseService(
                get_transaction()
            ).get_by_organization_contact_and_id(
                organization_id=organization_id,
                contact_id=current_contact.contact_id,
                pk=conversation_id,
            )
        except ConversationNotFound as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        knowledgebase = await KnowledgebaseService(
            get_transaction()
        ).find_conversation_knowledgebase(
            organization_id=organization_id,
            conversation_id=conversation_id,
        )
        if knowledgebase is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        try:
            job = await IngestionService(get_transaction()).get(
                job_id,
                knowledgebase.id,
                organization_id,
            )
        except IngestionError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
        if not _is_contact_upload(job, current_contact, conversation_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return _widget_ingestion_read(job)


async def _read_bounded_file(request: Request) -> bytes:
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            parsed_length = int(declared_length)
            if parsed_length < 0:
                raise ValueError
            if parsed_length > MAX_STORAGE_OBJECT_BYTES:
                raise _file_too_large()
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Content-Length is invalid.") from error

    raw = bytearray()
    async for block in request.stream():
        if len(raw) + len(block) > MAX_STORAGE_OBJECT_BYTES:
            raise _file_too_large()
        raw.extend(block)
    return bytes(raw)


def _file_too_large() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        detail=f"File exceeds the {MAX_STORAGE_OBJECT_BYTES} byte limit.",
    )


def _decode_filename(encoded_filename: str) -> str:
    try:
        return _safe_filename(unquote(encoded_filename, errors="strict"))
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=400, detail="File name is invalid.") from error


def _is_contact_upload(
    job,
    current_contact: CurrentContactSchema,
    conversation_id: UUID,
) -> bool:
    metadata = job.meta or {}
    return (
        job.scope == KnowledgeScope.CONVERSATION.value
        and str(job.scope_id) == str(conversation_id)
        and metadata.get("source_kind") == "conversation_upload"
        and metadata.get("uploaded_by_contact_id") == str(current_contact.contact_id)
    )


def _widget_ingestion_read(job) -> WidgetKnowledgeIngestionRead:
    state = job.state.value if hasattr(job.state, "value") else str(job.state)
    safe_error = None
    if state == "failed":
        safe_error = "This file could not be indexed."
    elif state == "cancelled":
        safe_error = "This file upload was cancelled."
    return WidgetKnowledgeIngestionRead(
        id=job.id,
        document_id=job.document_id,
        state=state,
        title=job.title,
        source_uri=job.source_uri,
        last_error=safe_error,
    )


def _safe_filename(filename: str) -> str:
    normalized = PurePath(filename.replace("\\", "/")).name.strip()
    if not normalized or len(normalized) > 512:
        raise HTTPException(status_code=400, detail="File name is invalid.")
    return normalized
