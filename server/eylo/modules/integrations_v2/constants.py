"""Stable persistence prefix and API tag for curated integrations."""

APP_TAG = "Curated Integrations"
APP_DB_PREFIX = "integration_v2_"
OAUTH_ROUTE_PREFIX = "/oauth"
OAUTH_CALLBACK_PATH = f"{OAUTH_ROUTE_PREFIX}/callback"

__all__ = [
    "APP_DB_PREFIX",
    "APP_TAG",
    "OAUTH_CALLBACK_PATH",
    "OAUTH_ROUTE_PREFIX",
]
