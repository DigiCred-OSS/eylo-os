"""Errors for the `stt` socket."""

class STTConnectionError(Exception):
    """Custom exception for connection errors."""

    pass


class STTConnectionClosed(STTConnectionError):
    """Custom exception for closed connection errors."""

    pass


class STTConnectionFailed(STTConnectionError):
    """Custom exception for connection failed errors."""

    pass
