"""Constants for the `members` domain."""

from eylo.common.config import settings

# Define constants
SECRET_KEY = settings.AUTH_SECRET_KEY
ALGORITHM = settings.AUTH_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.AUTH_ACCESS_TOKEN_EXPIRE_MINUTES

APP_DB_PREFIX = "member_"
APP_NAME = "members"
APP_TAG = "Members"
