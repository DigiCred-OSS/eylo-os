"""Shared utilities for OpenAI vendor adapters.

Contains functions that are identical between the Chat Completions adapter
(openai.py), the Responses API adapter (openai_responses.py), and the
Realtime API adapter (realtime/vendors/openai_realtime.py). All three APIs
share the same client, strict-mode schema requirements, and tool content
serialization.
"""

import logging
from typing import Any, Dict

from openai import AsyncOpenAI

from eylo.common.contracts.tool_platform import PlatformTool
from eylo.common.contracts.tool_record import ToolRecord
from eylo.common.utils.toon_serde import toon_encode

logger = logging.getLogger(__name__)

# ── Client ────────────────────────────────────────────────────────


def create_openai_client(api_key: str) -> AsyncOpenAI:
    """Build an authenticated client from explicitly resolved credentials."""
    return AsyncOpenAI(api_key=api_key)


# ── Strict-mode schema helpers ────────────────────────────────────


def ensure_strict_mode_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure a JSON schema is compatible with OpenAI's strict mode."""
    schema = schema.copy()

    if schema.get("type") == "object":
        schema["additionalProperties"] = False

        properties = schema.get("properties")
        if not isinstance(properties, dict):
            # Ensure ``properties`` always exists for object schemas.
            # Vendors like Groq reject schemas that have ``required``
            # without ``properties``.
            properties = {}
            schema["properties"] = properties

        for prop_name, prop_schema in properties.items():
            if isinstance(prop_schema, dict):
                properties[prop_name] = ensure_strict_mode_schema(prop_schema)

        # OpenAI strict mode: every property must be in ``required``.
        # Optional fields use null type (already handled by Pydantic's
        # anyOf generation) rather than being absent from ``required``.
        schema["required"] = list(properties.keys())

    elif schema.get("type") == "array":
        if "items" in schema and isinstance(schema["items"], dict):
            schema["items"] = ensure_strict_mode_schema(schema["items"])

    return schema


def extract_openai_function_declarations(
    tools: list[ToolRecord],
) -> list[Dict[str, Any]]:
    """Extract OpenAI-compatible function declarations from platform tools.

    Iterates *tools*, extracts name / description / strict-mode parameters
    from each ``ToolRecord.llm_config`` (``PlatformTool``), and applies
    ``ensure_strict_mode_schema`` to enforce additionalProperties: false
    at all levels.

    Args:
        tools: Platform tools with populated ``llm_config``.

    Returns:
        List of ``{"name", "description", "parameters"}`` dicts ready to
        be wrapped in the caller's API-specific format:

        - Chat Completions: ``{"type": "function", "function": {**d, "strict": True}}``
        - Responses API: ``{"type": "function", **d, "strict": True}``
        - Realtime API: ``{"type": "function", **d}``

    """
    declarations: list[Dict[str, Any]] = []

    for tool in tools:
        try:
            if not tool.llm_config:
                logger.warning("Tool %s has no llm_config, skipping", tool.id)
                continue

            platform_tool = tool.llm_config
            if not isinstance(platform_tool, PlatformTool):
                logger.error(
                    "Unexpected llm_config type for tool %s: %s",
                    tool.id,
                    type(tool.llm_config),
                )
                continue

            input_schema = ensure_strict_mode_schema(
                platform_tool.input_schema.to_json_schema()
            )
            declarations.append(
                {
                    "name": platform_tool.name,
                    "description": platform_tool.description,
                    "parameters": input_schema,
                }
            )
        except Exception as error:
            logger.error(
                "Tool transformation failed tool=%s error_type=%s",
                tool.id,
                type(error).__name__,
            )
            continue

    return declarations


# ── Tool content serialization ────────────────────────────────────


def serialize_tool_content(content: Any) -> str:
    """Serialize tool execution content to a string.

    Both Chat Completions and Responses API expect tool output as strings.
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, (dict, list)):
        return toon_encode(content)
    else:
        return str(content)


# ── Platform-side response accessors ──────────────────────────────
