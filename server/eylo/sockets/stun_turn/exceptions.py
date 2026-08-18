"""Exceptions for STUN/TURN services."""


class StunTurnError(Exception):
    """Base exception for STUN/TURN service errors."""

    pass


class StunTurnConnectionFailed(StunTurnError):
    """Exception raised when STUN/TURN service connection fails."""

    pass


class StunTurnCredentialsFailed(StunTurnError):
    """Exception raised when fetching STUN/TURN credentials fails."""

    pass
