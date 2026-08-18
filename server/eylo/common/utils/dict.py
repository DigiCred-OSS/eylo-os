"""Recursive dictionary merge and compact JSON helpers."""

import json
from typing import Any


def deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge two dictionaries.

    Args:
        base: The base dictionary to merge into.
        update: The dictionary containing updates.

    Returns:
        The merged dictionary.

    """
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def to_json_str(data: dict[str, Any]) -> str:
    """Convert a dictionary to a compact JSON string.

    Args:
        data: The dictionary to convert.

    Returns:
        A compact JSON string.

    """
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)
