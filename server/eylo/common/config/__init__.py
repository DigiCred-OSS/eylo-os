"""Deployment setting loading, validation, and derived connection URLs."""

__all__ = ["settings"]

import enum
import logging
import os
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from starlette.config import Config as EnvConfig

from eylo.common.config.utils import env_to_pydantic_type, ge


class Environment(str, enum.Enum):
    LOCAL = "local"
    PROD = "prod"


class HostingMode(str, enum.Enum):
    LOCAL = "local"
    DOCKER = "docker"


ENV = ge("ENV", "local").lower()
HOSTING_MODE = ge("HOSTING_MODE", "local").lower()
logger = logging.getLogger(__name__)


def get_variables(module_name):
    module = globals().get(module_name, None)
    book = {}
    if module:
        book = {
            key: value
            for key, value in module.__dict__.items()
            if not key.startswith("_")
        }
    return book


_config = get_variables("common")
_config.update({"ENV": ENV})
if ENV == Environment.LOCAL.value:
    from eylo.common.config.local import *
elif ENV == Environment.PROD.value:
    from eylo.common.config.prod import *


_base_path = os.path.dirname(os.path.realpath(__file__))


def _read_env_config(env_file: str):
    if not os.path.isfile(env_file):
        return
    _env_conf = EnvConfig(env_file)
    for k, v in _env_conf.file_values.items():
        _config[k] = v


env_file = None

# Use the actual ENV value, not hardcoded "local"
_env_base = ENV  # Use current environment (local or prod)
_env_conf = get_variables(_env_base)
_config.update(_env_conf)
env_file = f"{_base_path}/.env.{_env_base}"

if env_file:
    if HOSTING_MODE == HostingMode.DOCKER.value:
        env_file = f"{env_file}.docker"
    _read_env_config(env_file)


class EyloSettings(BaseModel):
    ENV: Environment = Environment.LOCAL
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    AUTH_SECRET_KEY: str
    ENCRYPTION_KEY: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
        repr=False,
    )
    AUTH_ALGORITHM: str
    AUTH_ACCESS_TOKEN_EXPIRE_MINUTES: int
    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None
    # derived keys
    DATABASE_URL: str = "postgresql+asyncpg://user:password@host:port/db"
    REDIS_URL: str = "redis://:password@host:port/db"
    # Database connection pool configuration
    DB_POOL_SIZE: int = 10  # Number of connections to keep in pool
    DB_POOL_MAX_OVERFLOW: int = 20  # Additional connections beyond pool_size
    DB_POOL_TIMEOUT: int = 30  # Timeout for acquiring a connection from pool
    DB_POOL_PRE_PING: bool = True  # Test connections before using them
    # Telephony provider credentials are org-scoped via the existing
    # modules/telephony/ provider config system.
    # Logging configuration
    LOG_LEVEL: int = logging.DEBUG
    DEBUG: bool = False
    # Worker configuration - separate from DEBUG to allow workers in production
    ENABLE_WORKERS: bool = False
    # LLM Streaming Configuration
    # Set to True to enable streaming responses from LLM vendors (real-time token-by-token)
    # Set to False to use traditional non-streaming responses (wait for complete response)
    # Default: False (streaming disabled for stability)
    ENABLE_LLM_STREAMING: bool = True
    # LLM Prompt Caching Configuration
    # Set to True to enable provider-side prompt caching where the adapter supports it.
    # Today this is explicit Anthropic-style cache_control handling (also inherited by
    # the Bedrock Claude adapter). Other vendors may report cache usage, but they do
    # not consume this flag as an explicit cache-control instruction.
    #
    # Cache hits depend on exact prompt-prefix stability. Avoid adding timestamps,
    # request IDs, non-deterministic tool ordering, or other per-request content before
    # the Anthropic breakpoints, otherwise the provider will treat the prefix as new.
    # Default: False (prompt caching disabled)
    ENABLE_PROMPT_CACHING: bool = True
    SERVER_DOMAIN: str | None = None
    API_BASE_URL: str | None = None
    # Public provider redirect for curated vendor OAuth.
    OAUTH_CALLBACK_URL: str | None = None
    FRONTEND_URL: str | None = None
    WIDGET_URL: str | None = None
    # Local-only standalone widget identity. Both values must name existing
    # rows; the browser cannot choose or override them.
    WIDGET_DEVELOPMENT_ORGANIZATION_ID: UUID | None = None
    WIDGET_DEVELOPMENT_CONTACT_ID: UUID | None = None
    # Trusted deployment override for a Twilio-compatible egress gateway or
    # deterministic local carrier. Per-org callers cannot set this URL.
    TWILIO_API_BASE_URL: str | None = None

    DEBUG_QUERY_LOGGING: bool = False

    # CORS — comma-separated allowed origins. Empty defaults to localhost
    # for local development. Set explicitly in production.
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]

    # Feature flags — parallel agents
    ENABLE_SPAWN_TASK_FNF: bool = False
    # Feature flags — voice
    ENABLE_REALTIME_VOICE: bool = True
    ENABLE_VOICE_RECORDING: bool = False
    # Trusted deployment mount. This does not select or configure a storage
    # provider; an org must still create, verify and explicitly bind one
    # filesystem config. The API can name only a namespace below this root.
    STORAGE_FILESYSTEM_ROOT: str | None = None
    # Exact operator-trusted OpenAI-compatible embedding base URLs. Org API
    # callers cannot send credentials or document text to any other custom host.
    EMBEDDING_BASE_URL_ALLOWLIST: str | None = None
    # Exact operator-trusted Cohere-compatible rerank endpoints. Voyage stays
    # fixed to its hosted endpoint; org API callers cannot redirect credentials
    # or retrieved passages to an arbitrary host.
    RERANKING_BASE_URL_ALLOWLIST: str | None = None

    # Feature flags — widget interfaces
    COMPOUND_WIDGET_TOOL_DESC_VERSION: int = 0
    # Feature flags — use cases
    IS_MOCK_MODE: bool = False

    @model_validator(mode="before")
    @classmethod
    def env_to_py(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        normalized_data = dict(data)
        for field_name, field_info in cls.model_fields.items():
            if field_name not in normalized_data:
                continue

            normalized_data[field_name] = env_to_pydantic_type(
                normalized_data[field_name], field_info.annotation
            )

        return normalized_data

    @model_validator(mode="after")
    def update_database_url(self):
        self.DATABASE_URL = f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        if self.REDIS_PASSWORD:
            self.REDIS_URL = f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            self.REDIS_URL = (
                f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        # Debugging - enable for local, disable for prod
        self.DEBUG = True if self.ENV == Environment.LOCAL else False
        # Set API base URL based on environment
        if not self.API_BASE_URL:
            self.API_BASE_URL = "http://localhost:8000/api"
        return self

    @model_validator(mode="after")
    def validate_widget_development_identity(self):
        organization_id = self.WIDGET_DEVELOPMENT_ORGANIZATION_ID
        contact_id = self.WIDGET_DEVELOPMENT_CONTACT_ID
        if (organization_id is None) != (contact_id is None):
            raise ValueError(
                "WIDGET_DEVELOPMENT_ORGANIZATION_ID and "
                "WIDGET_DEVELOPMENT_CONTACT_ID must be configured together."
            )
        if organization_id is not None and self.ENV is not Environment.LOCAL:
            raise ValueError(
                "Widget development identity can only be configured when ENV=local."
            )
        return self


_env_overrides = {
    field_name: os.environ[field_name]
    for field_name in EyloSettings.model_fields
    if field_name in os.environ
}
settings = EyloSettings(**(_config | _env_overrides))
logger.debug("Settings loaded for ENV=%s", settings.ENV)
