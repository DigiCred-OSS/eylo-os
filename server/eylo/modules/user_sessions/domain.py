"""User-session vocabulary and transition errors."""

from __future__ import annotations

from enum import StrEnum


class UserSessionEntryChannel(StrEnum):
    WIDGET = "widget"
    TELEPHONY = "telephony"
    API = "api"


class UserSessionState(StrEnum):
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    ENDED = "ended"
    FAILED = "failed"


TERMINAL_USER_SESSION_STATES = frozenset(
    {UserSessionState.ENDED, UserSessionState.FAILED}
)


class UserSessionError(Exception):
    """Base error for a refused user-session operation."""


class UserSessionNotFound(UserSessionError):
    """The requested session is absent from the caller's exact authority."""


class UserSessionTerminal(UserSessionError):
    """A terminal session cannot be resumed or changed."""


class UserSessionTransitionInvalid(UserSessionError):
    """The requested lifecycle transition is not valid from the current state."""

