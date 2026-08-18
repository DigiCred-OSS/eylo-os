"""Email Socket Exception Module.

This module defines custom exceptions for email socket operations,
providing a clear hierarchy for error handling across different email vendors.
"""


class EmailError(Exception):
    """Base exception for all email-related errors."""

    pass


class EmailSendError(EmailError):
    """Exception raised when email sending fails."""

    pass


class EmailValidationError(EmailError):
    """Exception raised when email validation fails."""

    pass


class EmailVendorError(EmailError):
    """Exception raised when vendor-specific errors occur."""

    pass


class EmailConfigurationError(EmailError):
    """Exception raised when email configuration is invalid."""

    pass


class EmailRateLimitError(EmailError):
    """Exception raised when rate limits are exceeded."""

    pass


class EmailAuthenticationError(EmailError):
    """Exception raised when authentication with email vendor fails."""

    pass
