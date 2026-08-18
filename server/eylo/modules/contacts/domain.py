"""Contact aggregate lifecycle and stable application failures."""

from enum import StrEnum

CONTACT_SUBJECT_TYPE = "contact"


class ContactLifecycle(StrEnum):
    """Whether a contact may enter new product work."""

    ACTIVE = "active"
    DELETION_PENDING = "deletion_pending"


class ContactActorKind(StrEnum):
    """Safe attribution vocabulary for contact lifecycle facts."""

    MEMBER = "member"
    CONTACT = "contact"
    SYSTEM = "system"


class ContactError(Exception):
    """Base class for expected contact use-case outcomes."""


class ContactNotFound(ContactError):
    """A contact reference does not resolve inside the organization."""


class ContactConflict(ContactError):
    """A requested mutation conflicts with an existing contact identity."""


class ContactDeletionPending(ContactConflict):
    """The contact is fenced from new work while deletion is pending."""


class ContactIdentityInvalid(ContactError, ValueError):
    """A supplied identifier cannot be represented by the contact contract."""
