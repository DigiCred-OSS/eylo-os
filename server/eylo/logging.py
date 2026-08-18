"""Process-wide structured logging configuration."""

import inspect
import logging
import sys

from loguru import logger

from eylo.common.config import settings
from eylo.common.redaction import RedactingLogFilter, redact_log_text


def init_logging():
    """Initialize Application Logging."""
    # Loguru's default sink enables ``diagnose`` for exceptions, which prints
    # frame locals. Request schemas can contain passwords, tokens, and raw user
    # data, so runtime sinks must never render locals even in local mode.
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        backtrace=False,
        diagnose=False,
    )

    handler = InterceptHandler()
    # Every record reaches Loguru through this handler, so a session that asked
    # for PII redaction gets it wherever the log statement lives.
    handler.addFilter(RedactingLogFilter())
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        handlers=[handler],
    )

    # Set logging levels for specific modules
    _loggers_level = {
        "uvicorn": logging.WARN,
        "uvicorn.access": logging.WARN,
        "uvicorn.error": logging.WARN,
        "sqlalchemy": logging.ERROR,
        "sqlalchemy.engine": logging.ERROR,
        "sqlalchemy.pool": logging.ERROR,
        "sqlalchemy.dialects": logging.ERROR,
        "sqlalchemy.orm": logging.ERROR,
        "fastapi": logging.WARN,
        "asyncio": logging.WARN,
        "starlette": logging.WARN,
        "numba.core": logging.WARN,
        "websockets": logging.INFO,
        "aiortc": logging.INFO,
        "aioice": logging.ERROR,  # Suppress ICE negotiation warnings
        "newrelic": logging.INFO,
        # Provider SDK DEBUG logs can serialize complete prompts, tool results,
        # sandbox commands, emails, and phone numbers. Platform adapters own
        # the safe operational metadata; third-party request bodies stay off
        # every runtime sink even when the application itself runs at DEBUG.
        "openai": logging.WARNING,
        "groq": logging.WARNING,
        "cerebras": logging.WARNING,
        "anthropic": logging.WARNING,
        "google.genai": logging.WARNING,
        "google.api_core": logging.WARNING,
        "sarvamai": logging.WARNING,
        "docker": logging.WARNING,
        "twilio": logging.WARNING,
        "plivo": logging.WARNING,
        "sendgrid": logging.WARNING,
        "aiosmtplib": logging.WARNING,
        "botocore": logging.WARNING,
        "aws_sdk_bedrock_runtime": logging.WARNING,
        "smithy_aws_core": logging.WARNING,
        "smithy_aws_event_stream": logging.WARNING,
        "smithy_core": logging.WARNING,
        "smithy_http": logging.WARNING,
        "urllib3": logging.WARNING,
        "httpx": logging.WARNING,
        "httpcore": logging.WARNING,
        "markdown_it": logging.WARNING,
    }
    for _logr, _lvl in _loggers_level.items():
        lg = logging.getLogger(_logr)
        lg.disabled = False
        lg.propagate = True
        lg.handlers = []
        lg.setLevel(_lvl)


class InterceptHandler(logging.Handler):
    """Log Interceptor Handler."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit Log Record."""
        # Get corresponding Loguru level if it exists.
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        message = redact_log_text(record.getMessage()) or ""
        exception_text = _redacted_exception_text(record)
        if exception_text:
            message = f"{message}\n{exception_text}"

        # Passing ``record.exc_info`` to Loguru would create a second, raw
        # rendering channel that bypasses the text redactor. Format once with
        # Python logging (which excludes frame locals), sanitize, then forward
        # the complete record as ordinary text.
        logger.opt(depth=depth).log(level, message)


def _redacted_exception_text(record: logging.LogRecord) -> str | None:
    """Format one exception without locals and apply the log text policy."""
    exception_text = record.exc_text
    if exception_text is None and record.exc_info and record.exc_info[0] is not None:
        exception_text = logging.Formatter().formatException(record.exc_info)
    return redact_log_text(exception_text)
