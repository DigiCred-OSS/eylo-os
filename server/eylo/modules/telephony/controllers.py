"""Controller for telephony management operations."""

from uuid import UUID

from fastapi import HTTPException

from eylo.common.exceptions import EntityNotFound
from eylo.common.schemas import PaginationParams
from eylo.modules.telephony.schemas import (
    PhoneNumberApiResponseSchema,
    PhoneNumberCreateSchema,
    PhoneNumberUpdateSchema,
    PhoneNumbersPaginated,
)
from eylo.modules.telephony.services import PhoneNumberService


class PhoneNumberController:
    def __init__(self):
        self.service = PhoneNumberService()

    def _verify_ownership(self, entity, organization_id: UUID) -> None:
        """Ensure the fetched entity belongs to the requesting organization."""
        if entity.organization_id != organization_id:
            raise HTTPException(status_code=404, detail="Not found.")

    async def get(
        self, phone_number_id: UUID, organization_id: UUID
    ) -> PhoneNumberApiResponseSchema:
        try:
            phone_number = await self.service.get_(phone_number_id)
            self._verify_ownership(phone_number, organization_id)
            return PhoneNumberApiResponseSchema.model_validate(phone_number)
        except EntityNotFound:
            raise HTTPException(
                status_code=404,
                detail=f"Phone number with ID {phone_number_id} not found.",
            )

    async def list(
        self,
        organization_id: UUID,
        pagination: PaginationParams,
        provider: str | None = None,
    ) -> PhoneNumbersPaginated:
        phone_numbers = await self.service.list_by_organization(
            organization_id=organization_id,
            limit=pagination.limit,
            offset=pagination.get_offset(),
            provider=provider,
        )
        total = await self.service.count_by_organization(
            organization_id, provider=provider
        )
        return PhoneNumbersPaginated(
            data=[
                PhoneNumberApiResponseSchema.model_validate(pn) for pn in phone_numbers
            ],
            total=total,
            limit=pagination.limit,
            page=pagination.page,
        )

    async def create(
        self, organization_id: UUID, request: PhoneNumberCreateSchema
    ) -> PhoneNumberApiResponseSchema:
        phone_number = await self.service.create(organization_id, request)
        return PhoneNumberApiResponseSchema.model_validate(phone_number)

    async def update(
        self,
        phone_number_id: UUID,
        request: PhoneNumberUpdateSchema,
        organization_id: UUID,
    ) -> PhoneNumberApiResponseSchema:
        try:
            phone_number = await self.service.get_(phone_number_id)
            self._verify_ownership(phone_number, organization_id)
            phone_number = await self.service.update(phone_number_id, request)
            return PhoneNumberApiResponseSchema.model_validate(phone_number)
        except EntityNotFound:
            raise HTTPException(
                status_code=404,
                detail=f"Phone number with ID {phone_number_id} not found.",
            )

    async def delete(
        self, phone_number_id: UUID, organization_id: UUID
    ) -> PhoneNumberApiResponseSchema:
        try:
            phone_number = await self.service.get_(phone_number_id)
            self._verify_ownership(phone_number, organization_id)
            phone_number = await self.service.soft_delete(phone_number_id)
            return PhoneNumberApiResponseSchema.model_validate(phone_number)
        except EntityNotFound:
            raise HTTPException(
                status_code=404,
                detail=f"Phone number with ID {phone_number_id} not found.",
            )
