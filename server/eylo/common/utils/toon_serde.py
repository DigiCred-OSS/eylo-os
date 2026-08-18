"""TOON serialization for model and collection context."""

from openai import BaseModel
from toon import encode, encode_pydantic


def toon_encode(data: BaseModel | dict | str | list) -> str:
    """Encode data using Toon encoding.

    Args:
        data: The data to encode, can be a Pydantic model, dict, str, or list.

    Returns:
        str: The Toon encoded string.

    """
    if isinstance(data, BaseModel):
        return encode_pydantic(data)
    if hasattr(data, "model_dump"):
        return encode(data.model_dump())
    return encode(data)
