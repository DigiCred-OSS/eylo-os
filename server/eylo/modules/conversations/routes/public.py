"""Explicitly deny unsupported unauthenticated conversation mutation paths."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

# Conversation creation and mutation require a principal-specific channel path.
# The hidden guards prevent dynamic private GET paths from turning an unsupported
# public POST into a method-disclosing 405 response.
router = APIRouter(tags=["Conversations"])


@router.post(
    "/{organization_id}/conversations/start",
    include_in_schema=False,
)
async def disabled_public_conversation_start(organization_id: UUID) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post(
    "/{organization_id}/conversations/{conversation_id}/{action}",
    include_in_schema=False,
)
async def disabled_public_conversation_action(
    organization_id: UUID,
    conversation_id: UUID,
    action: str,
) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
