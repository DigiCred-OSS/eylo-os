"""Transport orchestration for authenticated outbound voice calls."""

import logging
from typing import Any, Dict
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException, Request

from eylo.common.contracts.provider_config import ProviderConfigError
from eylo.common.revisions import DefinitionRevisionError
from eylo.modules.agents.exceptions import AgentNotFoundError
from eylo.pipelines.telephony.call_control import VoiceService

logger = logging.getLogger(__name__)


class VoiceController:
    """Controller for generic voice telephony operations.

    This controller handles the HTTP interface for voice operations,
    delegating business logic to the VoiceService.
    """

    def __init__(self):
        self.service = VoiceService()

    async def outbound_call(
        self,
        request: Request,
        organization_id: UUID,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        """Initiate a call through the agent's organization-owned number."""
        try:
            body = await request.json()
            to_number = body.get("to_number")
            agent_id_str = body.get("agent_id")
            initial_message = body.get("initial_message")
            context = body.get("context", {})
            idempotency_key = idempotency_key.strip()

            if not to_number:
                raise HTTPException(status_code=400, detail="Missing to_number")
            if not agent_id_str:
                raise HTTPException(status_code=400, detail="Missing agent_id")
            if not idempotency_key or len(idempotency_key) > 255:
                raise HTTPException(
                    status_code=400,
                    detail="A bounded Idempotency-Key header is required.",
                )

            try:
                agent_id = UUID(agent_id_str)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid agent_id format")

            return await self.service.initiate_outbound_call(
                call_id=uuid5(
                    NAMESPACE_URL,
                    f"eylo:telephony-call:v1:{organization_id}:{idempotency_key}",
                ),
                to_number=to_number,
                agent_id=agent_id,
                organization_id=organization_id,
                initial_message=initial_message,
                context=context,
            )

        except (HTTPException, ProviderConfigError):
            raise
        except AgentNotFoundError:
            raise HTTPException(status_code=404) from None
        except DefinitionRevisionError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except Exception as error:
            logger.error(
                "Outbound call request failed error_type=%s",
                type(error).__name__,
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to initiate outbound call. Check server logs.",
            ) from None
