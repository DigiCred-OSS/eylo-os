"""Vonage telephony provider module.

Exports:
- VonageService: Main telephony service for Vonage
- VonageMessageParser: Parser for Vonage binary audio protocol
"""

from eylo.sockets.telephony.vonage.service import (
    VonageMessageParser,
    VonageService,
)

__all__ = ["VonageService", "VonageMessageParser"]
