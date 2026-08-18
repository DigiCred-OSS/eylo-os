"""ASGI entry point for the Eylo API."""

import asyncio
import platform

from eylo.app import app

__all__ = ["app"]

if platform.system() != "Windows":
    try:
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass
