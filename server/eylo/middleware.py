"""Request-body sanitization middleware."""

import json

import nh3 as bleach
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class BleachSanitizeBodyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.json()
                sanitized = self._sanitize_dict(body)
                # Set sanitized body for downstream usage
                request._body = json.dumps(sanitized).encode("utf-8")
            except Exception:
                # Silent fail for non-JSON or empty bodies
                pass
        response = await call_next(request)
        return response

    def _sanitize_dict(self, data):
        if isinstance(data, dict):
            return {k: self._sanitize_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_dict(item) for item in data]
        elif isinstance(data, str):
            return bleach.clean(data)
        else:
            return data
