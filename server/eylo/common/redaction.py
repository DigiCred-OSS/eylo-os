"""Deterministic log and payload redaction helpers."""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from typing import Final

REDACTED: Final = "[redacted]"

# Shapes are kept narrow rather than "any long run of digits". A loose digit
# pattern also eats ISO dates and epoch timestamps, which is unacceptable when
# the same redactor runs over logs.
_EMAIL = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
# Four groups of four, however they are separated, plus the 13-19 digit variants.
_CARD = re.compile(r"\b\d{4}(?:[ -]?\d{4}){2}(?:[ -]?\d{1,7})\b")
# Either an explicit country code, or the 3-3-4 grouping, or a bare 10-15 run.
_PHONE = re.compile(
    r"(?<![\w.-])(?:\+\d{1,3}[ .-]?)?"
    r"(?:\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}|\d{10,15})"
    r"(?![\w.-])"
)
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_URL_CREDENTIAL = re.compile(
    r"(?i)(?P<prefix>[?&](?:api[_-]?key|access[_-]?token|token|secret|password|credential)=)"
    r"[^&#\s\"']*"
)


def _luhn(digits: str) -> bool:
    """Standard mod-10 check used by payment cards."""
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _redact_cards(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return REDACTED
        return match.group()

    return _CARD.sub(replace, text)


def redact(text: str | None) -> str | None:
    """Replace shaped personal data in `text`. Returns the input if nothing matches.

    Order matters: emails first, because an address can contain digit runs the
    phone pattern would otherwise claim; then cards, validated by Luhn; then
    the remaining fixed shapes.
    """
    if not text:
        return text

    redacted = _EMAIL.sub(REDACTED, text)
    redacted = _redact_cards(redacted)
    redacted = _SSN.sub(REDACTED, redacted)
    redacted = _IPV4.sub(REDACTED, redacted)
    redacted = _PHONE.sub(REDACTED, redacted)
    return redacted


def redact_url_credentials(text: str | None) -> str | None:
    """Redact named credential values embedded in URL query strings."""
    if not text:
        return text
    return _URL_CREDENTIAL.sub(r"\g<prefix>[redacted]", text)


def redact_log_text(text: str | None) -> str | None:
    """Apply the complete policy for text crossing the application log boundary."""
    redacted = redact_url_credentials(text)
    if redact_logs.get():
        redacted = redact(redacted)
    return redacted


def redact_value(value: object) -> object:
    """Redact strings anywhere inside a nested structure, preserving its shape.

    Tool inputs and outputs are arbitrary JSON, so the sensitive part may be
    several levels down.
    """
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {key: redact_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        redacted = [redact_value(item) for item in value]
        return type(value)(redacted) if isinstance(value, tuple) else redacted
    return value


# Set for the duration of a voice session whose agent asked for log redaction.
# A contextvar rather than an argument because the log sites that leak — vendor
# adapters in `sockets/`, the transcript writer — have no agent in scope and
# should not grow one just to log. asyncio copies the context into tasks
# spawned from the session, so per-session scoping survives the fan-out.
redact_logs: ContextVar[bool] = ContextVar("redact_logs", default=False)


class RedactingLogFilter(logging.Filter):
    """Always redact URL credentials; redact shaped PII for opted-in sessions.

    Attached to the one handler every record passes through, so a new log
    statement anywhere is covered without the author having to know. The
    alternative — redacting at each call site — silently fails to cover the
    site added next week, which is how transcript text reaches logs to begin
    with.

    Formatting happens here rather than being left to the handler: the
    sensitive value is usually a `%s` argument, so redacting only `msg` would
    miss it entirely.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        original_message = record.getMessage()
        message = redact_log_text(original_message)
        if message != original_message or redact_logs.get():
            record.msg = message
            record.args = None
        return True
