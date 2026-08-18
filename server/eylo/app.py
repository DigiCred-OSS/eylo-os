"""FastAPI application composition and lifecycle management."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from eylo.common.config import settings
from eylo.common.contracts.provider_config import ProviderConfigError
from eylo.common.database import cleanup_database
from eylo.common.models import register_models
from eylo.common.routes import private_router, public_router, widget_router
from eylo.listeners.py_events import ListenerProcessRole, setup_listeners
from eylo.middleware import BleachSanitizeBodyMiddleware
from eylo.modules.provider_configs.crypto import SecretCipherError
from eylo.modules.provider_configs.errors import NotConfiguredError
from eylo.modules.provider_configs.exception_handlers import (
    handle_not_configured,
    handle_provider_config_error,
    handle_secret_cipher_error,
)
from eylo.pipelines.composition import register_pipeline_extensions
from eylo.pipelines.webrtc.singleton import (
    start_webrtc_signaling,
    stop_webrtc_signaling,
)
from eylo.pipelines.websocket.singleton import (
    start_websocket_manager,
    stop_websocket_manager,
)

from .logging import init_logging

logger = logging.getLogger(__name__)


register_models()
register_pipeline_extensions()
setup_listeners(process_role=ListenerProcessRole.API)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Enhanced lifespan manager with reliable service startup and shutdown.

    This context manager ensures graceful initialization and cleanup
    of all services, with proper error handling and dependency ordering.

    Args:
        app (FastAPI): The FastAPI application instance.

    """
    # Initialize logging
    init_logging()

    try:
        # Start WebSocket manager
        logger.info("Starting WebSocket manager...")
        await start_websocket_manager()

        # Start WebRTC signaling service
        logger.info("Starting WebRTC signaling service...")
        await start_webrtc_signaling()

        logger.info("Application startup completed successfully")

        # Yield control back to FastAPI
        yield

    except Exception as error:
        logger.error(
            "Application startup failed error_type=%s",
            type(error).__name__,
        )
        raise
    finally:
        # Cleanup phase
        logger.info("Starting application shutdown...")

        # Clean shutdown for WebRTC signaling
        try:
            logger.info("Stopping WebRTC signaling service...")
            await stop_webrtc_signaling()
        except Exception as error:
            logger.error(
                "WebRTC signaling shutdown failed error_type=%s",
                type(error).__name__,
            )

        # Clean shutdown for WebSocket manager
        try:
            logger.info("Stopping WebSocket manager...")
            await stop_websocket_manager()
        except Exception as error:
            logger.error(
                "WebSocket manager shutdown failed error_type=%s",
                type(error).__name__,
            )

        # Clean shutdown for database connection pool
        await cleanup_database()

        logger.info("Application shutdown completed")


app = FastAPI(
    title="Eylo Server",
    description="Eylo Server API",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_exception_handler(NotConfiguredError, handle_not_configured)
app.add_exception_handler(ProviderConfigError, handle_provider_config_error)
app.add_exception_handler(SecretCipherError, handle_secret_cipher_error)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.debug(
        f"Incoming request: {request.method} {request.url.path}"
    )  # Log the path
    response = await call_next(request)
    return response


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(BleachSanitizeBodyMiddleware)

# Include routers
app.include_router(private_router, prefix="/api")
# Unauthenticated public routes use their own security dependencies.
app.include_router(public_router, prefix="/api")
# widget routes with session-based authentication
app.include_router(widget_router, prefix="/api")
# Mount the server landing page and the built widget assets.
server_dir = Path(os.path.dirname(os.path.dirname(__file__)))
project_root = server_dir.parent
widget_dist = project_root / "widget" / "preact-ui" / "dist"

app.mount("/static", StaticFiles(directory=str(server_dir / "static")), name="static")

# Serve widget from build directory (if it exists) or fallback to static
if widget_dist.exists():
    app.mount("/widget", StaticFiles(directory=str(widget_dist)), name="widget")
    logger.info(f"Serving widget from: {widget_dist}")
else:
    # Fallback to static directory
    static_widget = server_dir / "static" / "widget"
    if static_widget.exists():
        app.mount("/widget", StaticFiles(directory=str(static_widget)), name="widget")
        logger.info(f"Serving widget from: {static_widget}")
    else:
        logger.warning("Widget directory not found in either location")

@app.get("/")
def read_root():
    """Root endpoint for the Eylo Server."""
    return FileResponse(str(server_dir / "static" / "index.html"))


@app.get("/health")
async def health_check():
    """Health check endpoint for the Eylo Server."""
    return status.HTTP_200_OK
