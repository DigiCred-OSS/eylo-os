"""Shared async SQLAlchemy repository primitives."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Generic, List, Optional, Type, TypeVar

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect

from eylo.common.database import get_transaction
from eylo.common.models import Base

logger = logging.getLogger(__name__)

ModelClass = TypeVar("ModelClass", bound=Base)


class BaseORMRepository(ABC, Generic[ModelClass]):
    """Base ORM Repository."""

    def __init__(self, db: AsyncSession | None = None):
        """Init for the "common" platform."""
        self._db_session = db

    @property
    def db_session(self):
        """Database Session Property."""
        return self._db_session or get_transaction()

    @db_session.setter
    def db_session(self, db_session: AsyncSession):
        """Set Database Session."""
        self._db_session = db_session

    @property
    @abstractmethod
    def model(self) -> Type[ModelClass]:
        """Model for the "common" platform."""
        pass

    def _build_filters(self, **kwargs):
        """Build Query Filters."""
        filters = []
        for key, value in kwargs.items():
            filters.append(getattr(self.model, key) == value)
        return filters

    def _build_columns(self, columns: List[str]):
        """Build Column References."""
        return [getattr(self.model, column) for column in columns]

    def _build_select(
        self,
        filters: Optional[List] = None,
        columns: Optional[List[str]] = None,
        orders: Optional[List] = None,
    ):
        """Build SELECT Query."""
        _select = select(self.model)
        if filters:
            _select = _select.filter(*filters)
        if columns:
            _select = _select.with_only_columns(self._build_columns(columns))
        if orders:
            _select = _select.order_by(None).order_by(*orders)
        return _select

    async def get_(self, pk: Any, columns=[]) -> ModelClass | None:
        query = self._build_select([self.model.id == pk], columns)
        return (await self.db_session.execute(query)).scalar_one_or_none()

    async def get_multi_(self, pks: List[Any], columns=[]) -> List[ModelClass]:
        """Get Multiple Entities By Primary Keys."""
        if not pks:
            return []
        filters = [self.model.id.in_(pks)]
        query = self._build_select(filters, columns)
        return (await self.db_session.execute(query)).scalars().all()

    async def save_(self, entity: ModelClass) -> ModelClass:
        self.db_session.add(entity)
        await self.db_session.flush()
        await self.db_session.refresh(entity)
        return entity

    async def bulk_save_(self, entities: List[ModelClass]) -> List[ModelClass]:
        self.db_session.add_all(entities)
        await self.db_session.flush()
        for entity in entities:
            await self.db_session.refresh(entity)
        return entities

    async def partial_update_(self, entity: ModelClass) -> ModelClass:
        _pks = [key.name for key in inspect(self.model).primary_key]
        if not _pks:
            raise ValueError("Entity must have a primary key to update")
        _pk = _pks[0]  # Assuming single primary key for simplicity
        if not hasattr(entity, _pk):
            raise ValueError(
                f"Entity must have a primary key attribute '{_pk}' to update"
            )
        if not getattr(entity, _pk):
            raise ValueError(
                f"Entity primary key '{_pk}' cannot be None or empty for update"
            )
        _pk_value = getattr(entity, _pk)
        existing_entity = await self.get_(_pk_value)
        if not existing_entity:
            raise ValueError(f"Entity with primary key {_pks} does not exist")

        for key, value in entity.__dict__.items():
            if (
                not key.startswith("_")
                and key not in _pks
                and value is not None
                and value != getattr(existing_entity, key, None)
            ):
                logger.debug(
                    f"Updating field '{key}' from {getattr(existing_entity, key, None)} to {value}"
                )
                setattr(existing_entity, key, value)
        return await self.save_(existing_entity)

    async def delete_(self, entity: ModelClass, hard_delete: bool = False) -> None:
        if hard_delete:
            await self.db_session.execute(
                delete(self.model).where(self.model.id == entity.id)
            )
        else:
            entity.deleted = True
            await self.save_(entity)

    async def count_(self, filters: List) -> int:
        query = self._build_select(filters)
        return (
            await self.db_session.execute(query.with_only_columns(func.count()))
        ).scalar()

    async def filter_(
        self,
        filters: List,
        limit: int = 100,
        offset: int = 0,
        order_by: List | None = None,
        columns: List[str] | None = None,
    ) -> List[ModelClass]:
        query = self._build_select(filters, columns, order_by)
        return (
            (await self.db_session.execute(query.limit(limit).offset(offset)))
            .scalars()
            .all()
        )

    async def filter_one_(
        self, filters: List, columns: List[str] | None = None
    ) -> ModelClass | None:
        query = self._build_select(filters, columns)
        return (await self.db_session.execute(query)).scalar_one_or_none()

    async def filter_all_(
        self,
        filters: List,
        order_by: List | None = None,
        columns: List[str] | None = None,
    ) -> List[ModelClass]:
        query = self._build_select(filters, columns, order_by)
        _list = (await self.db_session.execute(query)).scalars().all()
        return _list

    async def list_all_(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: List | None = None,
        columns: List[str] | None = None,
        filters: List | None = None,
    ) -> List[ModelClass]:
        query = self._build_select(columns=columns, orders=order_by, filters=filters)
        return (
            (await self.db_session.execute(query.limit(limit).offset(offset)))
            .scalars()
            .all()
        )

    async def get_by_(self, key: str, value: str | int | float) -> ModelClass:
        if not hasattr(self.model, key):
            raise ValueError(
                f"Model {self.model.__tablename__} does not have a {key} field"
            )
        filters = [getattr(self.model, key) == value]
        return await self.filter_one_(filters)


# Utils


def map_model_to_schema(
    model_instance: ModelClass, schema_cls: Type[BaseModel]
) -> BaseModel:
    """Map the model instance to the Pydantic schema if the keys match."""
    model_data = {
        key: getattr(model_instance, key, None)
        for key in schema_cls.__annotations__.keys()
    }
    return schema_cls(**model_data)


def map_schema_to_model(
    model_cls: Type[ModelClass],
    schema_instance: BaseModel,
    schema_cls: Type[BaseModel] = None,
) -> ModelClass:
    """Map the Pydantic schema to the model instance."""
    model_instance = model_cls()
    if schema_cls and not isinstance(schema_instance, schema_cls):
        schema_instance = schema_cls.model_validate(
            schema_instance.model_dump(only=schema_cls.model_fields.keys())
        )
    for key, value in schema_instance.model_dump().items():
        setattr(model_instance, key, value)
    return model_instance
