"""Organization-scoped email delivery orchestration."""

from eylo.pipelines.email.delivery import (
    EmailDeliveryResult,
    EmailDeliveryUnsupported,
    require_organization_email,
    send_organization_email,
)
from eylo.pipelines.email.tool_execution import (
    SEND_EMAIL_TOOL_NAME,
    EmailToolExecutionOutcome,
    execute_agent_email_tool,
)

__all__ = [
    "EmailDeliveryResult",
    "EmailDeliveryUnsupported",
    "EmailToolExecutionOutcome",
    "SEND_EMAIL_TOOL_NAME",
    "execute_agent_email_tool",
    "require_organization_email",
    "send_organization_email",
]
