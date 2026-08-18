"""Shared platform errors and their HTTP response projection."""


class EntityNotFound(Exception):
    """EntityNotFound behavior for the "common" platform."""

    def __init__(self, message: str):
        """Init for the "common" platform."""
        super().__init__(message)
        self.message = message
