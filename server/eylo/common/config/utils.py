"""Environment-value parsing helpers."""

import os
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import TypeAdapter


def ge(var, default=None):
    return os.getenv(var) or default


def _annotation_contains_json_container(target_type: Any) -> bool:
    origin = get_origin(target_type)
    if origin in (list, dict):
        return True
    if origin in (UnionType, Union):
        return any(
            arg is not type(None) and _annotation_contains_json_container(arg)
            for arg in get_args(target_type)
        )
    return False


def env_to_pydantic_type(value: Any, target_type: Any):
    if value is None:
        return None

    origin = get_origin(target_type)
    args = get_args(target_type)
    is_optional = origin in (UnionType, Union) and type(None) in args
    expects_json_container = _annotation_contains_json_container(target_type)

    if isinstance(value, str):
        stripped_value = value.strip()
        if stripped_value == "" and is_optional:
            return None

        if expects_json_container:
            adapter = TypeAdapter(target_type)
            return adapter.validate_json(stripped_value)

        value = stripped_value

    adapter = TypeAdapter(target_type)
    return adapter.validate_python(value)
