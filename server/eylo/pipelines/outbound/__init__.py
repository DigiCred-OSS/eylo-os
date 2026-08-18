"""Pipeline-owned durable outbound-effect boundary."""

from eylo.pipelines.outbound.models import OutboundAttemptModel
from eylo.pipelines.outbound.service import OutboundAttemptService

__all__ = ["OutboundAttemptModel", "OutboundAttemptService"]
