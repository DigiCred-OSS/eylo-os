"""Typed failures for platform-owned executable tool definitions."""


class DefinitionDomainError(Exception):
    """Base error for organization-owned executable definitions."""


class DefinitionNotFoundError(DefinitionDomainError):
    """Raised when an org-scoped header or exact revision is unavailable."""


class InvalidDefinitionDraftError(DefinitionDomainError):
    """Raised when a draft cannot be published or executed."""


class ImmutableDefinitionFieldError(DefinitionDomainError):
    """Raised when an update attempts to change stable execution identity."""


__all__ = [
    "DefinitionDomainError",
    "DefinitionNotFoundError",
    "ImmutableDefinitionFieldError",
    "InvalidDefinitionDraftError",
]
