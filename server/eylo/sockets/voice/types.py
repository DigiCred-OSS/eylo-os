"""Common types for voice AI vendors.

These types are copied from LiveKit Agents to maintain compatibility.
"""

from typing import Any, TypeVar

# Sentinel value for optional parameters
NOT_GIVEN = TypeVar("NOT_GIVEN")
NOT_GIVEN = object()  # type: ignore

# Type alias for optional parameters
NotGivenOr = Any  # Simplified - full implementation would use TypeVar
