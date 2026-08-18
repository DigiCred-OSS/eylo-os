"""Async SQLAlchemy sessions, transactions, and post-commit event emission."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Any, AsyncGenerator, Callable, List, Optional, TypeVar

import sqlparse
from pydantic_core import to_jsonable_python
from sqlalchemy import event, exc, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from eylo.common.config import settings
from eylo.events.py_events.emitter import emit_ephemeral

logger = logging.getLogger(__name__)


def json_serializer(obj: Any) -> str:
    """Serialize objects to JSON format.

    This function is used as a custom JSON serializer for SQLAlchemy engine creation.
    It leverages pydantic's to_jsonable_python function to handle complex objects.

    Args:
        obj (Any): The object to be serialized.

    Returns:
        str: JSON string representation of the object.

    """
    return json.dumps(to_jsonable_python(obj))


# Create async SQLAlchemy engine with custom JSON serializer and connection pooling
async_engine_instance = create_async_engine(
    settings.DATABASE_URL,
    json_serializer=json_serializer,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_POOL_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    # Connection lifecycle management (prevents stale connections and memory leaks)
    pool_recycle=3600,  # Recycle connections after 1 hour (prevents stale connections)
    pool_reset_on_return="rollback",  # Reset connection state on return (ensures clean state)
    pool_use_lifo=True,  # Use LIFO for better memory locality (reduces working set)
    echo=False,  # Set to True for SQL query logging
)


# Event listener to log SQL shape without bound values.
@event.listens_for(async_engine_instance.sync_engine, "before_cursor_execute")
def _log_sql_queries(conn, cursor, statement, parameters, context, executemany):
    """Log SQL structure and parameter count without retaining row data.

    Bound values may contain credentials, message content, tool arguments, or
    contact data. Even explicit debug query logging must not copy them to logs.

    Args:
        conn: Database connection
        cursor: Database cursor
        statement: SQL statement string
        parameters: Query parameters
        context: Execution context
        executemany: Whether this is an executemany operation

    """
    if settings.DEBUG_QUERY_LOGGING:
        try:
            formatted_query = sqlparse.format(
                statement, reindent=True, keyword_case="upper", indent_width=2
            )
            logger.debug(
                "SQL query shape executemany=%s parameter_count=%d\n%s",
                executemany,
                len(parameters) if parameters else 0,
                formatted_query,
            )
        except Exception as error:
            logger.debug(
                "SQL query-shape formatting failed error_type=%s",
                type(error).__name__,
            )


# Create async session factory
async_session_factory: Callable[[], AsyncSession] = sessionmaker(
    async_engine_instance,
    class_=AsyncSession,
    expire_on_commit=False,
    # https://github.com/fastapi/fastapi/discussions/11321#discussioncomment-11772285
    # This tells SQLAlchemy: "When I call .close(), I mean actually close and return the connection to the pool, not just reset state for reuse."
    # https://github.com/fastapi/fastapi/discussions/11321#discussioncomment-14432166
    close_resets_only=False,  # Fully close connections on return to pool
)

# Context variable to store the current session
_session: ContextVar[Optional[AsyncSession]] = ContextVar("_session", default=None)
# New context variable for pending py_events
_pending_events: ContextVar[List] = ContextVar("pending_events")


def _emit_events(events: List):
    for e in events:
        logger.info(f"[EventEmittingSession] Emitting {e.__class__.__name__}")
        emit_ephemeral(e)
    events.clear()


class EventEmittingSession:
    """Wrapper around AsyncSession that automatically emits queued events on commit.

    This ensures that any code calling commit() will automatically broadcast events
    to WebSocket listeners without needing manual event emission.
    """

    def __init__(self, session: AsyncSession, events: List):
        self._session = session
        self._events = events

    async def commit(self):
        """Commit transaction and immediately emit all queued events."""
        await self._session.commit()
        # Emit all queued events immediately after successful commit
        _emit_events(self._events)

    def __getattr__(self, name):
        """Proxy all other attributes/methods to the underlying session."""
        return getattr(self._session, name)


@asynccontextmanager
async def start_transaction(
    *,
    connection_name: str | None = None,
    ro: bool = False,
) -> AsyncGenerator[AsyncSession, None]:
    """Asynchronous context manager to start a database transaction."""
    session: AsyncSession = async_session_factory()

    # Initialize empty events list and set in context
    py_events_: List = []  # type: ignore
    py_events_token_ = _pending_events.set(py_events_)

    # Wrap session with event-emitting behavior
    wrapped_session = EventEmittingSession(session, py_events_)
    token = _session.set(wrapped_session)  # type: ignore

    try:
        if connection_name:
            await session.execute(f"SET LOCAL application_name = '{connection_name}'")

        if ro:
            await session.execute(text("SET TRANSACTION READ ONLY"))

        yield wrapped_session  # type: ignore
        try:
            # Final commit will automatically emit any remaining events
            await wrapped_session.commit()
            _emit_events(py_events_)

        except exc.PendingRollbackError as error:
            logger.warning(
                "Database commit could not proceed: %s",
                type(error).__name__,
            )
    except asyncio.CancelledError:
        await session.rollback()
        raise
    except BaseException:
        await session.rollback()
        raise
    finally:
        await session.close()
        _session.reset(token)
        _pending_events.reset(py_events_token_)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a session from the transaction context manager."""
    async with start_transaction() as session:
        yield session


def get_transaction() -> AsyncSession:
    """Return an instance of Session local to the current async context.

    This function retrieves the current database session from the context variable.
    It should be used within a context where a session has been set using start_transaction.

    Returns:
        AsyncSession: The current database session.

    Raises:
        Exception: If no session is defined in the current context.

    """
    session = _session.get()
    if session is None:
        raise Exception("DB Session is not defined in the current context")

    return session


T = TypeVar("T", bound=Callable[..., Any])


def with_transaction(
    connection_name: str | None = None, ro: bool = False
) -> Callable[[T], T]:
    """Decorator for FastAPI routes to control database transactions."""

    def decorator(func: T) -> T:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with start_transaction(connection_name=connection_name, ro=ro):
                return await func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


async def get_db_session(
    *, connection_name: str | None = None, ro: bool = False
) -> AsyncGenerator[AsyncSession, None]:
    """Asynchronous generator for obtaining a database session."""
    try:
        session = get_transaction()
        yield session
    except Exception:
        async with start_transaction(connection_name=connection_name, ro=ro) as session:
            yield session


def register_ephemeral_event_post_txn(event):
    """Register a bounded local event for best-effort post-commit emission."""
    try:
        py_events_ = _pending_events.get()
        py_events_.append(event)
    except LookupError:
        # No active transaction context
        raise RuntimeError("Cannot register event: no active transaction")


async def cleanup_database():
    """Clean up the database connection pool."""
    try:
        logger.info("Disposing database connection pool...")
        await async_engine_instance.dispose()
        logger.info("Database connection pool disposed successfully")
    except Exception as error:
        logger.error(
            "Database engine disposal failed error_type=%s",
            type(error).__name__,
        )
