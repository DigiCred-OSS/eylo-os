"""Registered ISO-datetime validation system tool."""

import datetime


async def is_iso_datetime(
    datetime_str: str,
    *args,
    **kwargs,
) -> bool:
    """Return whether a string contains an ISO 8601 datetime with a timezone.

    Args:
        datetime_str: Candidate datetime string.

    Returns:
        ``True`` only when both time and timezone components are present.

    """
    if not datetime_str:
        return False

    # Check if string contains time component (required for ISO datetime)
    # Basic check - must have either 'T', 't', or a space followed by digits
    if not any(sep in datetime_str for sep in ["T", "t", " "]):
        return False

    # Check for timezone marker - proper ISO 8601 datetimes need timezone
    # Look for Z/z at the end or +/- for timezone offset
    if not (
        datetime_str.endswith("Z")
        or datetime_str.endswith("z")
        or any(marker in datetime_str[-6:] for marker in ["+", "-"])
    ):
        return False

    try:
        # Handle common variants of ISO format
        # 1. Convert 'Z' timezone indicator to '+00:00'
        # 2. Convert lowercase 't' to uppercase 'T' (fromisoformat is case sensitive)
        # 3. Convert space separator to 'T'
        normalized_str = datetime_str.replace("Z", "+00:00").replace("z", "+00:00")
        normalized_str = normalized_str.replace("t", "T")

        # Handle space separator (like "2023-01-01 12:00:00Z")
        if " " in normalized_str and "T" not in normalized_str:
            normalized_str = normalized_str.replace(
                " ", "T", 1
            )  # Replace only the first space

        dt = datetime.datetime.fromisoformat(normalized_str)

        # Ensure we have both date and time components
        has_time = (
            dt.hour != 0 or dt.minute != 0 or dt.second != 0 or dt.microsecond != 0
        )
        return (
            has_time or ":" in datetime_str
        )  # If time is all zeros, verify time component exists
    except ValueError:
        return False
