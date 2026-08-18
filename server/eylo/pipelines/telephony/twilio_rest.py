"""Composition seam exposing the Twilio REST adapter to application callers."""

from eylo.sockets.telephony.twilio.rest_client import (
    TwilioRestClient as TwilioRestClient,
)

__all__ = ["TwilioRestClient"]
