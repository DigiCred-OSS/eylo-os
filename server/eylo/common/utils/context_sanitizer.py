"""Sanitize untrusted context dicts before they enter the LLM pipeline.

Context dicts arrive from external clients (widget SDK, API, websocket)
and are injected into system prompts or user messages. They must be
sanitized to prevent:

- Prompt injection (instructions hidden in values)
- Payload bombing (oversized dicts consuming tokens / memory)
- Type confusion (unexpected objects reaching serialization)

Defenses applied:
- Total serialized size cap
- Key count and nesting depth limits
- String value truncation
- Strict type allowlist (str, int, float, bool, None, dict, list)
- HTML tag stripping via nh3 (covers websocket path that bypasses HTTP middleware)
"""

import json
import logging
from typing import Any, Dict, Optional

import nh3

logger = logging.getLogger(__name__)

# ── Limits ────────────────────────────────────────────────────────
MAX_CONTEXT_BYTES = 262_144  # 256 KB serialized
MAX_KEYS = 500
MAX_DEPTH = 6
MAX_STRING_VALUE_LENGTH = 1000
MAX_KEY_LENGTH = 100


def sanitize_context(
    context: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Sanitize an untrusted context dict for safe LLM injection.

    Args:
        context: Raw context dict from the client.

    Returns:
        Sanitized dict, or None if input is empty/invalid.

    """
    if not context or not isinstance(context, dict):
        return None

    sanitized = _sanitize_value(context, depth=0, path="")
    if not isinstance(sanitized, dict):
        return None

    # Enforce total serialized size by dropping trailing keys
    serialized = json.dumps(sanitized)
    if len(serialized) > MAX_CONTEXT_BYTES:
        original_size = len(serialized)
        keys = list(sanitized.keys())
        dropped_keys: list[str] = []
        while len(json.dumps(sanitized)) > MAX_CONTEXT_BYTES and keys:
            dropped_key = keys.pop()
            sanitized.pop(dropped_key)
            dropped_keys.append(dropped_key)
        logger.warning(
            "Context exceeded %d bytes (%d bytes). Dropped %d keys: %s",
            MAX_CONTEXT_BYTES,
            original_size,
            len(dropped_keys),
            dropped_keys,
        )
        if not sanitized:
            return None

    return sanitized


def _sanitize_value(value: Any, depth: int, path: str = "") -> Any:
    """Recursively sanitize a value, enforcing type and depth limits."""
    if depth > MAX_DEPTH:
        logger.debug(
            "Depth limit (%d) reached at '%s' — truncating nested data", MAX_DEPTH, path
        )
        return "[nested data truncated]"

    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value

    if isinstance(value, str):
        cleaned = nh3.clean(value, tags=set())
        if cleaned != value:
            logger.debug("HTML tags stripped at '%s'", path)
        if len(cleaned) > MAX_STRING_VALUE_LENGTH:
            logger.debug(
                "String truncated at '%s': %d → %d chars",
                path,
                len(cleaned),
                MAX_STRING_VALUE_LENGTH,
            )
            return cleaned[:MAX_STRING_VALUE_LENGTH] + "…"
        return cleaned

    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        total_keys = len(value)
        for i, (k, v) in enumerate(value.items()):
            if i >= MAX_KEYS:
                logger.warning(
                    "Key limit (%d) reached at '%s' — dropped %d keys",
                    MAX_KEYS,
                    path,
                    total_keys - MAX_KEYS,
                )
                break
            key = str(k)[:MAX_KEY_LENGTH]
            if len(str(k)) > MAX_KEY_LENGTH:
                logger.debug("Key name truncated at '%s': '%s'", path, str(k)[:200])
            sanitized[key] = _sanitize_value(
                v, depth + 1, path=f"{path}.{key}" if path else key
            )
        return sanitized

    if isinstance(value, list):
        total_items = len(value)
        if total_items > MAX_KEYS:
            logger.warning(
                "List limit (%d) reached at '%s' — dropped %d items",
                MAX_KEYS,
                path,
                total_items - MAX_KEYS,
            )
        return [
            _sanitize_value(item, depth + 1, path=f"{path}[{i}]")
            for i, item in enumerate(value[:MAX_KEYS])
        ]

    # Reject all other types (bytes, callables, custom objects, etc.)
    logger.debug(
        "Unsupported type %s at '%s' — coerced to string", type(value).__name__, path
    )
    return str(value)[:MAX_STRING_VALUE_LENGTH]
