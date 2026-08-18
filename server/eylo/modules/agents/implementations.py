"""Resolve registered first-party Agent implementation slugs."""

from __future__ import annotations

from typing import Final

# Slug -> what the implementation does, for the error message and the UI.
#
# These two were part of the hardcoded fan-out: they ran on every conversation
# whether or not anyone asked for them. As background agents they run only
# where an operator attaches them.
BACKGROUND_IMPLEMENTATIONS: Final[dict[str, str]] = {
    "title_generator": (
        "Names the conversation once it has enough substance, and writes "
        "conversation.title."
    ),
    "summary_generator": (
        "Compacts older messages into a SUMMARY message once the conversation "
        "approaches the model's context limit."
    ),
}


def is_registered(slug: str) -> bool:
    return slug in BACKGROUND_IMPLEMENTATIONS


def known_slugs() -> list[str]:
    return sorted(BACKGROUND_IMPLEMENTATIONS)
