"""Email config catalog."""

from __future__ import annotations

from enum import Enum

__all__ = ["EmailProviders"]


class EmailProviders(str, Enum):
    SMTP = "smtp"
    SENDGRID = "sendgrid"