"""Enumerations for the `mappers` domain."""

# Common Enums


from enum import Enum


class ConnectionKind(str, Enum):
    """ConnectionKind behavior for the "mappers" domain."""

    ORGANIZATION = "ORGANIZATION"
    CONTACT = "CONTACT"
