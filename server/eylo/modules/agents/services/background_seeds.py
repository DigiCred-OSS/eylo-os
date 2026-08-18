"""Application services for the `agents` domain."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from eylo.modules.agents.implementations import BACKGROUND_IMPLEMENTATIONS
from eylo.modules.agents.models import AgentKind

logger = logging.getLogger(__name__)

# Slug -> (display name, description). The description is what an operator
# reads when choosing what to attach, so it says what the agent does rather
# than how. Prompts are not seeded here: these two carry their prompts in
# code, which is what `implementation` means, and storing a second copy the
# runtime ignores would be a config field that does nothing.
SEEDED_BACKGROUND_AGENTS: dict[str, tuple[str, str]] = {
    "title_generator": ("Title Generator", BACKGROUND_IMPLEMENTATIONS["title_generator"]),
    "summary_generator": (
        "Summary Generator",
        BACKGROUND_IMPLEMENTATIONS["summary_generator"],
    ),
}


async def seed_background_agents(
    organization_id: UUID, db: Optional[AsyncSession] = None
) -> list[UUID]:
    """Create any missing first-party background agents. Returns their ids.

    Attachments are not created. An operator attaches what they want, which is
    the whole point of the phase.
    """
    from eylo.modules.agents.schemas.indb import AgentCreate
    from eylo.modules.agents.services.indb import AgentService

    service = AgentService(db)
    created: list[UUID] = []

    for slug, (name, description) in SEEDED_BACKGROUND_AGENTS.items():
        existing = await _find_by_slug(service, organization_id, slug)
        if existing is not None:
            continue

        agent = await service.create_(
            AgentCreate(
                organization_id=organization_id,
                name=name,
                description=description,
                kind=AgentKind.BACKGROUND,
                implementation=slug,
            )
        )
        created.append(agent.id)
        logger.info(
            "Seeded background agent %s (%s) for organization %s",
            slug,
            agent.id,
            organization_id,
        )

    return created


async def _find_by_slug(service, organization_id: UUID, slug: str):
    """Idempotency check. `None` is the ordinary answer on a first seed."""
    return await service.get_by_slug(slug=slug, organization_id=organization_id)
