"""Typed, non-executable template compilation and rendering."""

from __future__ import annotations

import html
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from uuid import UUID

from eylo.common.revisions import DefinitionRef

RENDERER_VERSION = "interpolation-v1"
MAX_TEMPLATE_BODY_CHARS = 64_000
MAX_RENDERED_CHARS = 64_000
MAX_VARIABLES = 64
MAX_VARIABLE_STRING_CHARS = 32_000

_VARIABLE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_PLACEHOLDER = re.compile(r"{{\s*([A-Za-z][A-Za-z0-9_]{0,63})\s*}}")


class TemplateError(Exception):
    """Base error for the template aggregate and renderer."""


class TemplateNotFoundError(TemplateError):
    """Raised for absent, deleted, or cross-organization template identity."""


class TemplateConflictError(TemplateError):
    """Raised when stable identity or optimistic draft state conflicts."""


class InvalidTemplateError(TemplateError):
    """Raised when a draft or render input violates the V1 template subset."""


class TemplateKind(str, Enum):
    AGENT_INSTRUCTIONS = "agent_instructions"
    CAMPAIGN_MESSAGE = "campaign_message"


class TemplateVariableType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"


class TemplateConsumerKind(str, Enum):
    CONVERSATIONAL_TEXT = "conversational_text"
    REALTIME_VOICE = "realtime_voice"
    BACKGROUND_AGENT = "background_agent"
    SWARM_AGENT = "swarm_agent"
    SANDBOX_AGENT = "sandbox_agent"
    CAMPAIGN_MESSAGE = "campaign_message"


class TemplateSegmentAuthority(str, Enum):
    AUTHORED_INSTRUCTION = "authored_instruction"
    RUNTIME_DATA = "runtime_data"


_AGENT_CONSUMERS = frozenset(
    {
        TemplateConsumerKind.CONVERSATIONAL_TEXT,
        TemplateConsumerKind.REALTIME_VOICE,
        TemplateConsumerKind.BACKGROUND_AGENT,
        TemplateConsumerKind.SWARM_AGENT,
        TemplateConsumerKind.SANDBOX_AGENT,
    }
)


@dataclass(frozen=True, slots=True)
class CompiledTemplate:
    body: str
    variables: Mapping[str, TemplateVariableType]

    def __post_init__(self) -> None:
        object.__setattr__(self, "variables", MappingProxyType(dict(self.variables)))

    def to_storage(self) -> dict[str, list[dict[str, str]]]:
        return {
            "variables": [
                {"name": name, "type": variable_type.value}
                for name, variable_type in self.variables.items()
            ]
        }


@dataclass(frozen=True, slots=True)
class TemplateSegment:
    authority: TemplateSegmentAuthority
    text: str
    variable_name: str | None = None


@dataclass(frozen=True, slots=True)
class RenderedTemplate:
    text: str
    segments: tuple[TemplateSegment, ...]
    renderer_version: str
    consumer_kind: TemplateConsumerKind
    variable_names: tuple[str, ...]
    template_ref: DefinitionRef | None = None
    template_id: UUID | None = None
    draft_version: int | None = None


def compile_template(body: str, variable_schema: Mapping[str, object]) -> CompiledTemplate:
    """Validate the complete declared V1 interpolation program."""
    if not isinstance(body, str):
        raise InvalidTemplateError("Template body must be text.")
    if not body or len(body) > MAX_TEMPLATE_BODY_CHARS:
        raise InvalidTemplateError(
            f"Template body must contain 1 to {MAX_TEMPLATE_BODY_CHARS} characters."
        )

    variables = _variable_types(variable_schema)
    placeholders = tuple(match.group(1) for match in _PLACEHOLDER.finditer(body))
    unsupported = _PLACEHOLDER.sub("", body)
    if "{{" in unsupported or "}}" in unsupported:
        raise InvalidTemplateError(
            "Template syntax supports only {{ variable_name }} interpolation."
        )
    placeholder_names = set(placeholders)
    declared_names = set(variables)
    if placeholder_names != declared_names:
        missing = sorted(placeholder_names - declared_names)
        unused = sorted(declared_names - placeholder_names)
        details = []
        if missing:
            details.append(f"undeclared placeholders: {', '.join(missing)}")
        if unused:
            details.append(f"unused variables: {', '.join(unused)}")
        raise InvalidTemplateError("Variable schema mismatch; " + "; ".join(details) + ".")
    return CompiledTemplate(body=body, variables=variables)


def render_template(
    compiled: CompiledTemplate,
    *,
    kind: TemplateKind | str,
    consumer_kind: TemplateConsumerKind | str,
    values: Mapping[str, object],
) -> RenderedTemplate:
    """Render atomically while retaining instruction/data provenance segments."""
    kind = TemplateKind(kind)
    consumer_kind = TemplateConsumerKind(consumer_kind)
    _require_consumer(kind, consumer_kind)
    if not isinstance(values, Mapping) or not all(
        isinstance(name, str) for name in values
    ):
        raise InvalidTemplateError("Template variables must be a string-keyed mapping.")
    expected = set(compiled.variables)
    provided = set(values)
    missing = sorted(expected - provided)
    unknown = sorted(provided - expected)
    if missing or unknown:
        details = []
        if missing:
            details.append(f"missing variables: {', '.join(missing)}")
        if unknown:
            details.append(f"unknown variables: {', '.join(unknown)}")
        raise InvalidTemplateError("Invalid render input; " + "; ".join(details) + ".")

    normalized = {
        name: _render_value(name, values[name], variable_type)
        for name, variable_type in compiled.variables.items()
    }
    segments: list[TemplateSegment] = []
    cursor = 0
    for match in _PLACEHOLDER.finditer(compiled.body):
        if match.start() > cursor:
            segments.append(
                TemplateSegment(
                    authority=TemplateSegmentAuthority.AUTHORED_INSTRUCTION,
                    text=compiled.body[cursor : match.start()],
                )
            )
        name = match.group(1)
        value = normalized[name]
        if consumer_kind in _AGENT_CONSUMERS:
            value = (
                f'<runtime-data name="{name}" trust="untrusted">'
                f"{html.escape(value)}"
                "</runtime-data>"
            )
        segments.append(
            TemplateSegment(
                authority=TemplateSegmentAuthority.RUNTIME_DATA,
                text=value,
                variable_name=name,
            )
        )
        cursor = match.end()
    if cursor < len(compiled.body):
        segments.append(
            TemplateSegment(
                authority=TemplateSegmentAuthority.AUTHORED_INSTRUCTION,
                text=compiled.body[cursor:],
            )
        )
    text = "".join(segment.text for segment in segments)
    if len(text) > MAX_RENDERED_CHARS:
        raise InvalidTemplateError(
            f"Rendered template exceeds {MAX_RENDERED_CHARS} characters."
        )
    return RenderedTemplate(
        text=text,
        segments=tuple(segments),
        renderer_version=RENDERER_VERSION,
        consumer_kind=consumer_kind,
        variable_names=tuple(compiled.variables),
    )


def _variable_types(
    variable_schema: Mapping[str, object],
) -> dict[str, TemplateVariableType]:
    if not isinstance(variable_schema, Mapping) or set(variable_schema) != {"variables"}:
        raise InvalidTemplateError(
            "Variable schema must contain only a variables list."
        )
    raw_variables = variable_schema["variables"]
    if not isinstance(raw_variables, list) or len(raw_variables) > MAX_VARIABLES:
        raise InvalidTemplateError(
            f"Variable schema supports at most {MAX_VARIABLES} variables."
        )
    variables: dict[str, TemplateVariableType] = {}
    for raw_variable in raw_variables:
        if not isinstance(raw_variable, Mapping) or set(raw_variable) != {
            "name",
            "type",
        }:
            raise InvalidTemplateError(
                "Each variable requires exactly name and type."
            )
        name = raw_variable["name"]
        if not isinstance(name, str) or not _VARIABLE_NAME.fullmatch(name):
            raise InvalidTemplateError(
                "Variable names must be 1 to 64 ASCII letters, digits, or underscores "
                "and start with a letter."
            )
        if name in variables:
            raise InvalidTemplateError(f"Duplicate template variable: {name}.")
        try:
            variables[name] = TemplateVariableType(raw_variable["type"])
        except (TypeError, ValueError):
            raise InvalidTemplateError(
                f"Unsupported type for template variable {name}."
            ) from None
    return variables


def _render_value(
    name: str,
    value: object,
    variable_type: TemplateVariableType,
) -> str:
    if variable_type is TemplateVariableType.STRING:
        if not isinstance(value, str) or len(value) > MAX_VARIABLE_STRING_CHARS:
            raise InvalidTemplateError(
                f"Variable {name} must be text no longer than "
                f"{MAX_VARIABLE_STRING_CHARS} characters."
            )
        return value
    if variable_type is TemplateVariableType.BOOLEAN:
        if not isinstance(value, bool):
            raise InvalidTemplateError(f"Variable {name} must be a boolean.")
        return "true" if value else "false"
    if variable_type is TemplateVariableType.INTEGER:
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidTemplateError(f"Variable {name} must be an integer.")
        return str(value)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidTemplateError(f"Variable {name} must be a number.")
    if not math.isfinite(value):
        raise InvalidTemplateError(f"Variable {name} must be finite.")
    return str(value)


def _require_consumer(
    kind: TemplateKind,
    consumer_kind: TemplateConsumerKind,
) -> None:
    if kind is TemplateKind.AGENT_INSTRUCTIONS and consumer_kind in _AGENT_CONSUMERS:
        return
    if (
        kind is TemplateKind.CAMPAIGN_MESSAGE
        and consumer_kind is TemplateConsumerKind.CAMPAIGN_MESSAGE
    ):
        return
    raise InvalidTemplateError(
        f"Template kind {kind.value} cannot render for {consumer_kind.value}."
    )


__all__ = [
    "CompiledTemplate",
    "InvalidTemplateError",
    "RENDERER_VERSION",
    "RenderedTemplate",
    "TemplateConflictError",
    "TemplateConsumerKind",
    "TemplateError",
    "TemplateKind",
    "TemplateNotFoundError",
    "TemplateSegment",
    "TemplateSegmentAuthority",
    "TemplateVariableType",
    "compile_template",
    "render_template",
]
