"""Email utility tool for agent-triggered notifications."""

from typing import Any

from pydantic import EmailStr


async def send_email(
    to_email: EmailStr,
    subject: str,
    text_body: str,
    *args,
    html_body: str | None = None,
    ctx=None,
    **kwargs,
) -> dict[str, Any]:
    """Reject dispatch that has no committed TOOL_USE effect owner."""
    del to_email, subject, text_body, args, html_body, kwargs
    if ctx is None or getattr(ctx, "conversation", None) is None:
        raise ValueError("Email delivery requires conversation context.")
    raise RuntimeError("Email delivery requires the durable conversation tool runner.")
