"""Linear OAuth scopes, named as Linear names them."""

from __future__ import annotations

READ = "read"
WRITE = "write"
ISSUES_CREATE = "issues:create"
COMMENTS_CREATE = "comments:create"

OAUTH_SCOPES: tuple[str, ...] = (READ, WRITE, ISSUES_CREATE, COMMENTS_CREATE)

__all__ = ["COMMENTS_CREATE", "ISSUES_CREATE", "OAUTH_SCOPES", "READ", "WRITE"]
