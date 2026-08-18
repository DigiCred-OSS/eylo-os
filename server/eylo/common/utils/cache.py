"""Async cache decorator backed by Redis.

Usage:
    @async_cache_for(timeout=300)
    async def fetch_weather(city: str, date: str) -> dict:
        ...

Cache key is built from the function name + all args/kwargs, hashed
with MD5. If the same function is called with identical parameters
within the TTL window, the cached result is returned.

Designed for the tools layer — tool calls with identical parameters
return cached results instead of re-executing.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "eylo:fn_cache"


def _build_cache_key(fn_name: str, *args: Any, **kwargs: Any) -> str:
    """Build a deterministic Redis key from function name + arguments.

    Uses JSON serialization (sorted keys) for consistent ordering,
    falls back to str() for non-serializable objects.
    """
    parts: list[str] = [fn_name]
    for arg in args:
        try:
            parts.append(json.dumps(arg, sort_keys=True, default=str))
        except (TypeError, ValueError):
            parts.append(str(arg))
    for key in sorted(kwargs):
        parts.append(key)
        try:
            parts.append(json.dumps(kwargs[key], sort_keys=True, default=str))
        except (TypeError, ValueError):
            parts.append(str(kwargs[key]))

    digest = hashlib.md5("|".join(parts).encode()).hexdigest()
    return f"{_CACHE_PREFIX}:{fn_name}:{digest}"


def async_cache_for(timeout: int = 300, ignore_params: tuple[str, ...] = ()):
    """Decorator that caches async function results in Redis.

    Args:
        timeout: TTL in seconds (default 300 = 5 minutes).
        ignore_params: Keyword argument names to exclude from the cache key
            (e.g., 'ctx' which changes every call but doesn't affect output).

    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Filter out ignored params for key generation
            cache_kwargs = {k: v for k, v in kwargs.items() if k not in ignore_params}
            key = _build_cache_key(
                f"{fn.__module__}.{fn.__qualname__}", *args, **cache_kwargs
            )

            try:
                from eylo.common.redis import get_redis_client

                client = get_redis_client()
                cached = await client.get(key)
                if cached is not None:
                    logger.debug("Cache hit: %s", key)
                    return json.loads(cached)["v"]
            except Exception:
                # Redis down → skip cache, execute function
                logger.debug("Cache read failed for %s, executing function", key)

            result = await fn(*args, **kwargs)

            try:
                from eylo.common.redis import get_redis_client

                client = get_redis_client()
                await client.set(
                    key, json.dumps({"v": result}, default=str), ex=timeout
                )
            except Exception:
                logger.debug("Cache write failed for %s", key)

            return result

        # Expose for testing
        wrapper.cache_key_fn = lambda *a, **kw: _build_cache_key(
            f"{fn.__module__}.{fn.__qualname__}",
            *a,
            **{k: v for k, v in kw.items() if k not in ignore_params},
        )
        return wrapper

    return decorator
