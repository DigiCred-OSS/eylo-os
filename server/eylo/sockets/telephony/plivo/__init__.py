"""Plivo telephony provider module.

Production-ready implementation based on bolna-ai patterns.
"""

from eylo.sockets.telephony.plivo.service import PlivoMessageParser, PlivoService

__all__ = ["PlivoService", "PlivoMessageParser"]
