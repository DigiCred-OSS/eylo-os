"""Shared utilities for socket vendor adapters."""

from __future__ import annotations

from typing import TypeAlias

JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]
JSONDict: TypeAlias = dict[str, JSONValue]

_GEMINI_STRIP_KEYS = frozenset(
    {"additionalProperties", "additional_properties", "title", "$defs"}
)
_MAX_GEMINI_REF_DEPTH = 10


def clean_schema_for_gemini(schema: JSONDict) -> JSONDict:
    """Prepare a JSON schema for Gemini function declarations.

    Gemini rejects some Pydantic-generated metadata and also fails on unresolved
    local ``$ref`` pointers in function declaration schemas. This utility keeps
    the normalization shared between the classic Gemini LLM adapter and the
    Gemini Live realtime adapter.

    Args:
        schema: JSON schema dict (typically from Pydantic model_json_schema or
            PlatformToolInputSchema.to_json_schema).

    Returns:
        Cleaned schema dict compatible with Gemini's function declaration format.

    """
    defs = _extract_schema_definitions(schema)
    return _clean_schema_dict(schema, defs, depth=0)


def _extract_schema_definitions(schema: JSONDict) -> dict[str, JSONDict]:
    raw_defs = schema.get("$defs")
    if not isinstance(raw_defs, dict):
        return {}

    definitions: dict[str, JSONDict] = {}
    for name, definition in raw_defs.items():
        if isinstance(name, str) and isinstance(definition, dict):
            definitions[name] = definition
    return definitions


def _resolve_local_schema_ref(
    ref: str,
    defs: dict[str, JSONDict],
) -> JSONDict | None:
    if not ref.startswith("#/$defs/"):
        return None

    ref_name = ref[len("#/$defs/") :]
    return defs.get(ref_name)


def _clean_schema_dict(
    node: JSONDict,
    defs: dict[str, JSONDict],
    depth: int,
) -> JSONDict:
    ref = node.get("$ref")
    if isinstance(ref, str):
        if depth >= _MAX_GEMINI_REF_DEPTH:
            return {"type": "object"}

        resolved = _resolve_local_schema_ref(ref, defs)
        if resolved is None:
            return {"type": "object"}

        return _clean_schema_dict(resolved, defs, depth + 1)

    cleaned: JSONDict = {}
    for key, value in node.items():
        if key in _GEMINI_STRIP_KEYS:
            continue
        cleaned[key] = _clean_schema_value(value, defs, depth)
    return cleaned


def _clean_schema_value(
    value: JSONValue,
    defs: dict[str, JSONDict],
    depth: int,
) -> JSONValue:
    if isinstance(value, dict):
        return _clean_schema_dict(value, defs, depth)

    if isinstance(value, list):
        return [_clean_schema_value(item, defs, depth) for item in value]

    return value
