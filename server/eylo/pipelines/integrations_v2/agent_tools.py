"""Project curated registry tools into published Agent tool contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from eylo.modules.integrations_v2.schemas.indb import CuratedToolInDb
from eylo.modules.tools.models import ToolExecutionMode, ToolKind
from eylo.modules.tools.schemas.indb import ToolInDb
from eylo.modules.tools.schemas.platform import PlatformTool, PlatformToolInputSchema

from .contracts import CuratedToolSpec
from .registry import CuratedRegistry, load_vendors


def curated_tool_llm_config(spec: CuratedToolSpec) -> PlatformTool:
    """Build the model-visible contract for one curated tool from its code."""
    return PlatformTool(
        name=spec.qualified_name,
        description=spec.description,
        input_schema=PlatformToolInputSchema.model_validate(
            spec.input_model.model_json_schema()
        ),
    )


def project_curated_tool(
    *,
    row: CuratedToolInDb,
    spec: CuratedToolSpec,
) -> ToolInDb:
    """Project one curated tool row plus its registry spec into a `ToolInDb`.

    Built with `model_construct` because the projection is assembled from two
    already-validated sources and has no persisted counterpart to validate
    against.
    """
    now = datetime.now(timezone.utc)
    return ToolInDb.model_construct(
        id=row.id,
        organization_id=row.organization_id,
        deleted=False,
        created_at=now,
        updated_at=now,
        name=spec.qualified_name,
        slug=spec.qualified_name,
        kind=ToolKind.CURATED,
        display_name=spec.display_name,
        description=spec.description,
        wire_id=spec.wire_id,
        llm_config=curated_tool_llm_config(spec),
        executor_config={},
        execution_mode=ToolExecutionMode(row.execution_mode.value),
        mcp_server_id=None,
        mcp_server_revision=None,
    )


def project_curated_tools(
    *,
    rows: list[CuratedToolInDb],
    registry: CuratedRegistry | None = None,
) -> list[ToolInDb]:
    """Project every row this deployment still carries a binding for.

    A row whose binding disappeared in a deploy is skipped rather than raised
    on: it must not reach a model as a callable tool, and a rollback should not
    take an agent's whole tool list down with it.
    """
    registry = registry or load_vendors()
    projected: list[ToolInDb] = []
    for row in rows:
        spec = registry.tool(row.wire_id)
        if spec is None:
            continue
        projected.append(project_curated_tool(row=row, spec=spec))
    return projected


def curated_tool_ids(rows: list[CuratedToolInDb]) -> set[UUID]:
    """Row ids for the curated tools an organization has materialized."""
    return {row.id for row in rows}


__all__ = [
    "curated_tool_ids",
    "curated_tool_llm_config",
    "project_curated_tool",
    "project_curated_tools",
]
