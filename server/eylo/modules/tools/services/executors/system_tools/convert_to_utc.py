"""Registered UTC-conversion system tool."""

from datetime import datetime, timezone

import pytz


async def convert_to_utc(
    datetime_str: str,
    timezone_name: str = "UTC",
    datetime_format: str = None,
    *args,
    **kwargs,
) -> str:
    """Convert a datetime string from a named timezone to UTC ISO 8601.

    Args:
        datetime_str: Local datetime, such as ``2025-02-19T10:30:00``.
        timezone_name: IANA timezone, such as ``America/New_York``.
        datetime_format: Optional ``strptime`` format for non-ISO input.

    Returns:
        Equivalent UTC datetime with a ``Z`` suffix.

    Raises:
        ValueError: The datetime or timezone cannot be parsed.

    """
    # Parse the user's local time as a datetime object
    if datetime_format:
        # Use custom format
        local_datetime = datetime.strptime(datetime_str, datetime_format)
    else:
        # Use ISO format
        local_datetime = datetime.fromisoformat(datetime_str.replace("Z", ""))

    # Get the timezone object for the user's timezone
    try:
        user_timezone = pytz.timezone(timezone_name)
    except pytz.exceptions.UnknownTimeZoneError:
        raise ValueError(f"Unknown timezone: {timezone_name}")

    # Localize the datetime to the specified timezone
    local_datetime = user_timezone.localize(local_datetime, is_dst=None)

    # Convert to UTC
    utc_datetime = local_datetime.astimezone(timezone.utc)

    # Format as an ISO string with Z suffix and return
    result = utc_datetime.isoformat().replace("+00:00", "Z")
    return result
