"""Authenticated, payload-free health surface for both event delivery classes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from eylo.common.database import get_transaction, start_transaction
from eylo.events.durable.health import query_event_delivery_health
from eylo.listeners.py_events import listener_manifest_health
from eylo.modules.auth.schemas import CurrentUserSchema
from eylo.modules.auth.services.auth_service import get_current_user
from eylo.pipelines.durable_events.manifest import durable_event_consumer_manifest

router = APIRouter(prefix="/events", tags=["Event health"])


class DurableConsumerHealthResponse(BaseModel):
    consumer_name: str
    event_type: str
    event_version: int


class UnsupportedConsumerHealthResponse(DurableConsumerHealthResponse):
    delivery_count: int


class DurableDeliveryHealthResponse(BaseModel):
    observed_at: datetime
    total_count: int
    pending_count: int
    running_count: int
    succeeded_count: int
    dead_letter_count: int
    oldest_pending_age_seconds: int | None
    unsupported_delivery_count: int
    registered_consumers: tuple[DurableConsumerHealthResponse, ...]
    unsupported_consumers: tuple[UnsupportedConsumerHealthResponse, ...]


class LocalListenerHealthResponse(BaseModel):
    manifest_version: int
    process_role: str
    delivery_class: str
    healthy: bool
    handler_count: int
    event_count: int
    handler_ids: tuple[str, ...]


class EventHealthResponse(BaseModel):
    durable: DurableDeliveryHealthResponse
    local: LocalListenerHealthResponse


@router.get("/health", response_model=EventHealthResponse)
async def get_event_health(
    current_user: Annotated[CurrentUserSchema, Depends(get_current_user)],
) -> EventHealthResponse:
    """Return tenant-safe backlog/failure facts plus process registrations."""
    consumer_manifest = durable_event_consumer_manifest()
    async with start_transaction(ro=True):
        durable = await query_event_delivery_health(
            get_transaction(),
            organization_id=current_user.organization_id,
            registered_consumers=consumer_manifest,
        )

    local = listener_manifest_health()
    if local is None:
        raise RuntimeError("Local listener manifest was not initialized.")

    return EventHealthResponse(
        durable=DurableDeliveryHealthResponse(
            observed_at=durable.observed_at,
            total_count=durable.total_count,
            pending_count=durable.pending_count,
            running_count=durable.running_count,
            succeeded_count=durable.succeeded_count,
            dead_letter_count=durable.dead_letter_count,
            oldest_pending_age_seconds=durable.oldest_pending_age_seconds,
            unsupported_delivery_count=durable.unsupported_delivery_count,
            registered_consumers=tuple(
                DurableConsumerHealthResponse(
                    consumer_name=item.consumer_name,
                    event_type=item.event_type,
                    event_version=item.event_version,
                )
                for item in durable.registered_consumers
            ),
            unsupported_consumers=tuple(
                UnsupportedConsumerHealthResponse(
                    consumer_name=item.consumer_name,
                    event_type=item.event_type,
                    event_version=item.event_version,
                    delivery_count=item.delivery_count,
                )
                for item in durable.unsupported_consumers
            ),
        ),
        local=LocalListenerHealthResponse(
            manifest_version=local.manifest_version,
            process_role=local.process_role.value,
            delivery_class=local.delivery_class.value,
            healthy=local.healthy,
            handler_count=local.handler_count,
            event_count=local.event_count,
            handler_ids=local.handler_ids,
        ),
    )


__all__ = ["EventHealthResponse", "get_event_health", "router"]
