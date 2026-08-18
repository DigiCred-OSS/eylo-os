"""PostgreSQL types that are part of Eylo's declared schema."""

from sqlalchemy.types import UserDefinedType


class VectorType(UserDefinedType):
    """Dimension-flexible pgvector column used across configured spaces."""

    cache_ok = True

    def get_col_spec(self, **_kwargs: object) -> str:
        return "vector"


__all__ = ["VectorType"]
