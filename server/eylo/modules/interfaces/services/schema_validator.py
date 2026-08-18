"""Application services for the `interfaces` domain."""

import hashlib
import json
import logging
from typing import Any, Dict, List

from pydantic import ValidationError

from eylo.modules.interfaces.schemas.api import (
    ALL_COMPOUND_COMPONENT_TYPES,
    COMPOUND_MAX_COMPONENTS,
    COMPOUND_MAX_DEPTH,
    LAYOUT_COMPONENT_TYPES,
    CompoundWidgetNode,
    CompoundWidgetPayload,
    WidgetAlertPayload,
    WidgetButtonGroupPayload,
    WidgetCardListPayload,
    WidgetCatalogEntry,
    WidgetDatePickerPayload,
    WidgetDividerProps,
    WidgetFormPayload,
    WidgetImagePayload,
    WidgetProgressPayload,
    WidgetRowProps,
    WidgetSectionProps,
    WidgetStackProps,
    WidgetTablePayload,
    WidgetTextPayload,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Payload validation cache — deterministic, in-process, bounded LRU dict.
# Keyed by MD5 of the JSON-serialized payload so identical component trees
# skip Pydantic + tree-integrity re-validation.
# ---------------------------------------------------------------------------

_VALIDATION_CACHE_MAX = 64
_validation_cache: Dict[str, Any] = {}


def _payload_cache_key(raw: Dict[str, Any]) -> str:
    """Deterministic hash of a compound widget payload dict."""
    serialized = json.dumps(raw, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()


class CompoundWidgetSchemaValidatorService:
    """Validation service for compound_render_widget tool payloads.

    Validates the compound adjacency-list payload and each individual
    component node against the per-component schema.  Also owns the
    widget catalog used for LLM tool descriptions.
    """

    TOOL_NAME = "compound_render_widget"

    def __init__(self) -> None:
        self._catalog = self._build_catalog()
        self._content_schema_map = {
            "form": WidgetFormPayload,
            "button_group": WidgetButtonGroupPayload,
            "card_list": WidgetCardListPayload,
            "date_picker": WidgetDatePickerPayload,
            "alert": WidgetAlertPayload,
            "text": WidgetTextPayload,
            "image": WidgetImagePayload,
            "progress": WidgetProgressPayload,
            "table": WidgetTablePayload,
        }
        self._layout_props_map = {
            "stack": WidgetStackProps,
            "row": WidgetRowProps,
            "section": WidgetSectionProps,
            "divider": WidgetDividerProps,
        }

    def _build_catalog(self) -> Dict[str, WidgetCatalogEntry]:
        """Build the form catalog entry for LLM tool descriptions."""

        def string_schema(optional: bool = False) -> Dict[str, Any]:
            return {"type": "string", "optional": optional}

        def number_schema(optional: bool = False) -> Dict[str, Any]:
            return {"type": "number", "optional": optional}

        def boolean_schema(optional: bool = False) -> Dict[str, Any]:
            return {"type": "boolean", "optional": optional}

        def any_schema(optional: bool = False) -> Dict[str, Any]:
            return {"type": "any", "optional": optional}

        option_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["value", "label"],
            "properties": {
                "value": string_schema(),
                "label": string_schema(),
                "description": string_schema(True),
            },
        }

        field_validation_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "minLength": number_schema(True),
                "maxLength": number_schema(True),
                "min": number_schema(True),
                "max": number_schema(True),
                "pattern": string_schema(True),
                "message": string_schema(True),
                "minDate": string_schema(True),
                "maxDate": string_schema(True),
            },
        }

        form_payload_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["component", "props"],
            "properties": {
                "component": {"type": "string", "enum": ["form"]},
                "props": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title", "fields"],
                    "properties": {
                        "title": string_schema(),
                        "description": string_schema(True),
                        "fields": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["type", "name", "label"],
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": [
                                            "text",
                                            "email",
                                            "phone",
                                            "number",
                                            "textarea",
                                            "select",
                                            "radio",
                                            "checkbox",
                                            "date",
                                            "time",
                                            "datetime",
                                        ],
                                    },
                                    "name": string_schema(),
                                    "label": string_schema(),
                                    "placeholder": string_schema(True),
                                    "required": boolean_schema(True),
                                    "defaultValue": any_schema(True),
                                    "options": {
                                        "type": "array",
                                        "optional": True,
                                        "items": option_schema,
                                        "minItems": 1,
                                    },
                                    "validation": {
                                        **field_validation_schema,
                                        "optional": True,
                                    },
                                },
                            },
                        },
                        "submitLabel": string_schema(True),
                        "cancelLabel": string_schema(True),
                    },
                },
            },
        }

        return {
            "form": WidgetCatalogEntry(
                component="form",
                version="1",
                status="active",
                description="Multi-field form for collecting structured input.",
                schema=form_payload_schema,
                when_to_use=[
                    "collecting multiple related fields",
                    "booking or lead capture flows",
                    "survey-style information collection with varied input controls",
                ],
                required_props=["title", "fields"],
                rules=[
                    "select and radio fields must include options",
                    "each field needs a stable name",
                    "use validation.pattern for named formats such as email, phone, or url when needed",
                ],
                example_payload=WidgetFormPayload.model_validate(
                    {
                        "component": "form",
                        "props": {
                            "title": "Tell us about your onboarding needs",
                            "fields": [
                                {
                                    "type": "text",
                                    "name": "name",
                                    "label": "Your name",
                                    "required": True,
                                },
                                {
                                    "type": "select",
                                    "name": "goal",
                                    "label": "What would you like help with?",
                                    "required": True,
                                    "options": [
                                        {"value": "setup", "label": "Initial setup"},
                                        {
                                            "value": "migration",
                                            "label": "Migration planning",
                                        },
                                        {
                                            "value": "training",
                                            "label": "Team training",
                                        },
                                    ],
                                },
                                {
                                    "type": "number",
                                    "name": "team_size",
                                    "label": "Approximate team size",
                                    "validation": {"min": 1, "max": 500},
                                },
                                {
                                    "type": "datetime",
                                    "name": "preferred_time",
                                    "label": "Preferred meeting time",
                                    "required": True,
                                },
                            ],
                            "submitLabel": "Continue",
                            "cancelLabel": "Skip for now",
                        },
                    }
                ).model_dump(exclude_none=True, by_alias=True),
            ),
            "button_group": WidgetCatalogEntry(
                component="button_group",
                version="1",
                status="active",
                description="Quick-choice buttons for single-select decisions.",
                schema={
                    "type": "object",
                    "required": ["component", "props"],
                    "properties": {
                        "component": {"type": "string", "enum": ["button_group"]},
                        "props": {
                            "type": "object",
                            "required": ["buttons"],
                            "properties": {
                                "question": string_schema(True),
                                "buttons": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "object",
                                        "required": ["value", "label"],
                                        "properties": {
                                            "value": string_schema(),
                                            "label": string_schema(),
                                            "variant": {
                                                "type": "string",
                                                "optional": True,
                                                "enum": [
                                                    "primary",
                                                    "secondary",
                                                    "destructive",
                                                    "ghost",
                                                    "outline",
                                                    "link",
                                                ],
                                            },
                                        },
                                    },
                                },
                                "layout": {
                                    "type": "string",
                                    "optional": True,
                                    "enum": ["horizontal", "vertical"],
                                },
                            },
                        },
                    },
                },
                when_to_use=[
                    "yes/no or multiple-choice questions",
                    "quick-select from a small set of options",
                    "action confirmations",
                ],
                required_props=["buttons"],
                rules=[
                    "button values must be unique",
                    "keep to 2-5 buttons for best UX",
                    "use variant to differentiate primary from secondary actions",
                ],
                example_payload=WidgetButtonGroupPayload.model_validate(
                    {
                        "component": "button_group",
                        "props": {
                            "question": "How would you like to proceed?",
                            "buttons": [
                                {
                                    "value": "schedule",
                                    "label": "Schedule a call",
                                    "variant": "primary",
                                },
                                {"value": "email", "label": "Send me details"},
                                {
                                    "value": "skip",
                                    "label": "Not now",
                                    "variant": "ghost",
                                },
                            ],
                        },
                    }
                ).model_dump(exclude_none=True, by_alias=True),
            ),
            "card_list": WidgetCatalogEntry(
                component="card_list",
                version="1",
                status="active",
                description="Selectable list of rich cards for browsing and choosing items.",
                schema={
                    "type": "object",
                    "required": ["component", "props"],
                    "properties": {
                        "component": {"type": "string", "enum": ["card_list"]},
                        "props": {
                            "type": "object",
                            "required": ["cards"],
                            "properties": {
                                "title": string_schema(True),
                                "cards": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "object",
                                        "required": ["id", "title"],
                                        "properties": {
                                            "id": string_schema(),
                                            "title": string_schema(),
                                            "description": string_schema(True),
                                            "image": string_schema(True),
                                            "price": string_schema(True),
                                            "badge": string_schema(True),
                                            "features": {
                                                "type": "array",
                                                "optional": True,
                                                "items": string_schema(),
                                            },
                                        },
                                    },
                                },
                                "selectionMode": {
                                    "type": "string",
                                    "optional": True,
                                    "enum": ["single", "multiple"],
                                },
                            },
                        },
                    },
                },
                when_to_use=[
                    "product or plan selection",
                    "browsable lists with rich detail per item",
                    "comparison-style choices",
                ],
                required_props=["cards"],
                rules=[
                    "each card must have a unique id",
                    "image URLs must use https://",
                    "use badge for status or highlights",
                ],
                example_payload=WidgetCardListPayload.model_validate(
                    {
                        "component": "card_list",
                        "props": {
                            "title": "Choose a plan",
                            "selectionMode": "single",
                            "cards": [
                                {
                                    "id": "starter",
                                    "title": "Starter",
                                    "description": "For small teams",
                                    "price": "$9/mo",
                                    "features": ["5 users", "10 GB storage"],
                                },
                                {
                                    "id": "pro",
                                    "title": "Pro",
                                    "description": "For growing teams",
                                    "price": "$29/mo",
                                    "badge": "Popular",
                                    "features": [
                                        "25 users",
                                        "100 GB storage",
                                        "Priority support",
                                    ],
                                },
                            ],
                        },
                    }
                ).model_dump(exclude_none=True, by_alias=True),
            ),
            "date_picker": WidgetCatalogEntry(
                component="date_picker",
                version="1",
                status="active",
                description="Single date, time, or datetime picker.",
                schema={
                    "type": "object",
                    "required": ["component", "props"],
                    "properties": {
                        "component": {"type": "string", "enum": ["date_picker"]},
                        "props": {
                            "type": "object",
                            "required": ["label", "name"],
                            "properties": {
                                "label": string_schema(),
                                "name": string_schema(),
                                "description": string_schema(True),
                                "mode": {
                                    "type": "string",
                                    "optional": True,
                                    "enum": ["date", "time", "datetime"],
                                },
                                "placeholder": string_schema(True),
                                "required": boolean_schema(True),
                                "defaultValue": string_schema(True),
                                "submitLabel": string_schema(True),
                            },
                        },
                    },
                },
                when_to_use=[
                    "scheduling appointments or meetings",
                    "collecting a single date or time value",
                    "deadline or due-date selection",
                ],
                required_props=["label", "name"],
                rules=[
                    "mode defaults to date if omitted",
                    "time mode defaultValue uses HH:MM format (24h)",
                    "date mode defaultValue uses YYYY-MM-DD format",
                ],
                example_payload=WidgetDatePickerPayload.model_validate(
                    {
                        "component": "date_picker",
                        "props": {
                            "label": "Preferred meeting date",
                            "name": "meeting_date",
                            "mode": "datetime",
                            "required": True,
                            "submitLabel": "Confirm",
                        },
                    }
                ).model_dump(exclude_none=True, by_alias=True),
            ),
            "alert": WidgetCatalogEntry(
                component="alert",
                version="1",
                status="active",
                description="Informational or warning banner for contextual messages.",
                schema={
                    "type": "object",
                    "required": ["component", "props"],
                    "properties": {
                        "component": {"type": "string", "enum": ["alert"]},
                        "props": {
                            "type": "object",
                            "required": ["message"],
                            "properties": {
                                "title": string_schema(True),
                                "message": string_schema(),
                                "dismissible": boolean_schema(True),
                                "severity": {
                                    "type": "string",
                                    "optional": True,
                                    "enum": ["info", "success", "warning", "error"],
                                },
                            },
                        },
                    },
                },
                when_to_use=[
                    "showing important notices before or after forms",
                    "success/error feedback after an action",
                    "contextual warnings or instructions",
                ],
                required_props=["message"],
                rules=[
                    "severity defaults to info if omitted",
                    "use title for emphasis, message for details",
                    "combine with other components inside a stack layout",
                ],
                example_payload=WidgetAlertPayload.model_validate(
                    {
                        "component": "alert",
                        "props": {
                            "title": "Important",
                            "message": "Your session will expire in 5 minutes.",
                            "severity": "warning",
                        },
                    }
                ).model_dump(exclude_none=True, by_alias=True),
            ),
        }

    def validate_compound_payload(self, raw: Dict[str, Any]) -> CompoundWidgetPayload:
        """Parse and validate a full compound widget payload.

        Results are cached by payload hash — identical component trees skip
        re-validation.  Cache holds up to 64 recent payloads in-process.

        1. Pydantic structural validation (IDs, root, cycles, depth, orphans)
        2. Per-node component+props validation against the typed schema
        """
        cache_key = _payload_cache_key(raw)
        cached = _validation_cache.get(cache_key)
        if cached is not None:
            logger.debug("compound validation cache hit: %s", cache_key[:16])
            return cached

        try:
            payload = CompoundWidgetPayload.model_validate(raw)
        except ValidationError as exc:
            hint = self._build_compound_validation_hint(exc)
            raise ValueError(hint) from exc

        # Validate each node's props against its component schema
        for node in payload.components:
            self._validate_node(node)

        _validation_cache[cache_key] = payload
        # Evict oldest entry if over capacity
        if len(_validation_cache) > _VALIDATION_CACHE_MAX:
            _validation_cache.pop(next(iter(_validation_cache)))

        return payload

    def _validate_node(self, node: CompoundWidgetNode) -> None:
        """Validate a single compound node's props against its component schema."""
        if node.component in self._layout_props_map:
            props_model = self._layout_props_map[node.component]
            try:
                props_model.model_validate(node.props)
            except ValidationError as exc:
                raise ValueError(
                    f"Layout component '{node.id}' (type '{node.component}') "
                    f"has invalid props: {exc}"
                ) from exc
        elif node.component in self._content_schema_map:
            payload_model = self._content_schema_map[node.component]
            try:
                payload_model.model_validate(
                    {"component": node.component, "props": node.props}
                )
            except ValidationError as exc:
                raise ValueError(
                    f"Component '{node.id}' (type '{node.component}') "
                    f"has invalid props: {exc}"
                ) from exc
        else:
            supported = sorted(
                set(self._content_schema_map.keys())
                | set(self._layout_props_map.keys())
            )
            raise ValueError(
                f"Component '{node.id}' has unknown type '{node.component}'. "
                f"Valid types: {', '.join(supported)}"
            )

    def _build_compound_validation_hint(self, exc: ValidationError) -> str:
        """Build an LLM-actionable error for compound structural failures."""
        issues: List[str] = []
        for err in exc.errors():
            loc = " -> ".join(str(p) for p in err["loc"] if p != "__root__")
            issues.append(f"  - {loc}: {err['msg']}")

        parts = ["Compound widget validation failed:"]
        parts.extend(issues)
        parts.append(
            f"Constraints: max {COMPOUND_MAX_COMPONENTS} components, "
            f"max depth {COMPOUND_MAX_DEPTH}. "
            f"Layout types: {', '.join(sorted(LAYOUT_COMPONENT_TYPES))}. "
            f"Content types: {', '.join(sorted(self._content_schema_map.keys()))}."
        )
        return "\n".join(parts)

    def _format_component_section(
        self,
        entry: WidgetCatalogEntry,
        props_schema: Dict[str, Any],
    ) -> str:
        """Format a single component's documentation for the tool description.

        Kept compact: name, one-line description, props with types/enums,
        and key rules. No per-component examples — the compound example
        at the end of the tool description is sufficient.
        """
        lines: List[str] = []
        lines.append(f"**{entry.component}** — {entry.description}")

        required_props = props_schema.get("required", [])
        prop_defs = props_schema.get("properties", {})

        prop_parts: List[str] = []
        for prop_name, prop_def in prop_defs.items():
            req_marker = " (required)" if prop_name in required_props else ""
            detail = self._format_prop_detail(prop_name, prop_def)
            if detail:
                # Multi-line detail: insert marker on the first line
                detail_lines = detail.split("\n")
                detail_lines[0] = f"{detail_lines[0]}{req_marker}"
                prop_parts.append("\n".join(detail_lines))
            else:
                p_type = prop_def.get("type", "any")
                prop_parts.append(f"- {prop_name}: {p_type}{req_marker}")

        if prop_parts:
            lines.append("Props:")
            lines.extend(prop_parts)

        if entry.rules:
            lines.append(f"Rules: {'; '.join(entry.rules)}.")

        return "\n".join(lines)

    @staticmethod
    def _format_prop_detail(prop_name: str, prop_def: Dict[str, Any]) -> str:
        """Return a human-readable one-liner for a prop schema, or empty string."""
        p_type = prop_def.get("type", "")

        if "enum" in prop_def:
            return f"- {prop_name}: one of {prop_def['enum']}"

        if p_type == "array" and "items" in prop_def:
            items = prop_def["items"]
            if items.get("type") == "object" and "properties" in items:
                field_keys = list(items["properties"].keys())
                required_keys = items.get("required", [])
                optional_keys = [k for k in field_keys if k not in required_keys]
                parts = [f"- {prop_name}: array of objects."]
                if required_keys:
                    parts.append(f"  Required keys: {', '.join(required_keys)}.")
                if optional_keys:
                    parts.append(f"  Optional keys: {', '.join(optional_keys)}.")
                for fk, fv in items["properties"].items():
                    if "enum" in fv:
                        parts.append(f"  {fk}: one of {fv['enum']}")
                    if fv.get("type") == "array" and "items" in fv:
                        nested = fv["items"]
                        if nested.get("type") == "object" and "properties" in nested:
                            nested_keys = list(nested["properties"].keys())
                            parts.append(
                                f"  {fk}: array of objects with keys {nested_keys}"
                            )
                return "\n".join(parts)

        return ""

    def compile_descriptions(self, idx: int) -> str:
        """Return the header/preamble for tool description version *idx*.

        Each entry is a self-contained intro + layout reference.  The rest
        of the description (content components, constraints, example) is
        assembled by ``build_tool_description()``.

        Versions:
            0 — Compact reference (default).  Dense, scannable, ~4800 chars
                total.  Leads with the required input format.
            1 — Minimal.  Bare-minimum schema-only description.  ~1300 chars.
                For models that choke on anything longer.
            2 — Original verbose (~12500 chars).  Full prose with use-case
                examples, composition patterns, behavioral rules, and
                per-component JSON examples.
        """
        descriptions: List[str] = []

        # --- v0: compact reference ---
        descriptions.append(f"""\
Render interactive UI in the chat widget. Use to collect structured input OR display data visually.

## Required Input

Return a JSON object with exactly two keys:

1. "components": array of component objects (1–{COMPOUND_MAX_COMPONENTS} items)
   Each component: {{ "id": string, "component": string, "props": JSON string, "children": [child_ids] }}
   - "props" must be a JSON-serialized object string, e.g. "{{\\"title\\": \\"Hello\\"}}"
   - "children" is ONLY for layout components (stack, row, section)

2. "root": string — must match one component's id

## Layout Components (structure only — use children to nest other components)

- **stack**: vertical layout. Props: spacing (optional): xs|sm|md|lg|xl
- **row**: horizontal layout. Props: spacing (optional), align (optional): start|center|end|stretch
- **section**: grouped content. Props: title (optional), description (optional), collapsible (optional, default false)
- **divider**: visual separator. Props: label (optional). No children.

## Content Components (leaves — MUST NOT have children)

""")

        # --- v1: minimal schema-only ---
        descriptions.append(f"""\
Build a UI component tree. Input: {{"components": [...], "root": "<root_id>"}}.

Each component: {{"id": string, "component": string, "props": JSON string, "children": [child_ids]}}.
"props" must be a JSON-serialized object string, e.g. "{{\\"title\\": \\"Hello\\"}}".
children is ONLY for layout types: stack, row, section, divider.
All other types are leaves (no children).

Max {COMPOUND_MAX_COMPONENTS} components, max depth {COMPOUND_MAX_DEPTH}. IDs must be unique. Must be a valid tree.

## Components

Layout: stack (spacing?), row (spacing?, align?), section (title?, description?, collapsible?), divider (label?)

""")

        # --- v2: original verbose (pre-optimization baseline) ---
        descriptions.append(f"""\
## compound_render_widget — Rich Interactive UI Tool

### Purpose
Render structured, interactive UI layouts in the user's chat widget. Use this tool both to **collect information** (forms, selections, date pickers) and to **present information** (tables, cards, alerts, progress indicators, formatted text) in a visually rich, organized manner.

This tool is your primary mechanism for delivering structured content to the user. Whenever plain text would be harder to read, less organized, or less actionable — use this tool instead.

---

## When to Use (PREFERRED)

You SHOULD use `compound_render_widget` when ANY of these are true:

### Collecting Information
- You need structured input from the user (forms, selections, date pickers)
- The input requires validation (types, required fields, enums, constraints)
- You are gathering multiple related pieces of information

### Presenting Information
- You want to display data in a table, card list, or structured layout
- You are showing progress through a multi-step flow
- You want to highlight important information with alerts or callouts
- You are presenting options the user should choose from (card selection)
- The response would benefit from visual hierarchy (headings, sections, dividers)
- You are summarizing or comparing data that would be hard to read as plain text

### Examples — Data Collection
- Signup or onboarding forms
- Booking or scheduling (date/time + details)
- Configuration or settings forms
- Survey or feedback collection
- Multi-field search or filter inputs

### Examples — Data Presentation
- Order summary or confirmation (table + alert)
- Product or plan comparison (card list)
- Step-by-step progress tracker (progress + sections)
- Structured report or data summary (table + text)
- Important notices or warnings (alert + text)
- Search results or recommendations (card list + text)

---

## When NOT to Use

Do NOT use this tool if:
- A short, simple text response is sufficient (one-liners, greetings)
- You are asking a single yes/no or open-ended question
- The conversation is purely conversational with no structure needed

---

## Mental Model

You are building a tree of UI components:

- Exactly ONE root component
- Layout components define structure
- Content components (forms, tables, cards, alerts, text) are leaves

### Construction Strategy

1. Decide what to present: collecting input, displaying data, or both
2. Define all leaf components (forms, tables, alerts, text, cards)
3. Group them using layout components (stack, row, section)
4. Assign a single root that contains everything

---

## Output Format

Return:

- `components`: array of objects
  Each object has:
  - `id`: string
  - `component`: string
  - `props`: JSON string (a JSON-serialized object, e.g. "{{\\"title\\": \\"Hello\\"}}")
  - `children`: array of child IDs (ONLY for layout components)

- `root`: string (must match one component ID)

---

## Constraints (STRICT — MUST FOLLOW)

- Maximum {COMPOUND_MAX_COMPONENTS} components
- Maximum depth: {COMPOUND_MAX_DEPTH}
- All component IDs MUST be unique
- ONLY layout components may have children
- ALL children must reference valid component IDs
- The structure MUST be a valid tree:
  - No cycles
  - Exactly one root
  - Every component must be reachable from root

---

## Component Types

### Layout Components (STRUCTURE ONLY)

#### stack
Vertical layout (top to bottom)

Props:
- spacing: xs | sm | md | lg | xl (optional)

Children:
- ordered list of child IDs

---

#### row
Horizontal layout (left to right)

Props:
- spacing: xs | sm | md | lg | xl (optional)
- align: start | center | end | stretch (optional)

Children:
- ordered list of child IDs

---

#### section
Grouped content with optional metadata

Props:
- title: string (optional)
- description: string (optional)
- collapsible: boolean (default false)

Children:
- ordered list of child IDs

---

#### divider
Visual separator

Props:
- label: string (optional)

Children:
- NONE

---

## Functional Components (LEAVES)

- Inputs, buttons, alerts, tables, cards, text, images, progress — all are leaves
- MUST NOT have children
- MUST be placed inside layout components

---

## Validation Requirements

When collecting input:

- Include validation constraints where applicable
- Mark required fields clearly
- Ensure structure aligns with expected backend schema
- Prefer explicit field types over generic inputs

---

## Composition Patterns

### Standard Form (collecting input)

stack
 ├── section (title/description)
 │    ├── input
 │    ├── input
 │    └── input
 └── row
      ├── submit button
      └── cancel button

---

### Data Presentation (displaying information)

stack
 ├── text (heading/summary)
 ├── table (structured data)
 └── alert (key takeaway or next step)

---

### Form with Context (collect + display)

stack
 ├── alert (important notice)
 ├── section (form fields)
 └── row (actions)

---

### Comparison / Selection

stack
 ├── text (explanation)
 ├── card_list (options to choose from)
 └── alert (selection guidance)

---

### Multi-section Report

stack
 ├── text (title)
 ├── section (group 1: summary)
 ├── divider
 ├── section (group 2: details)
 ├── divider
 └── section (group 3: next steps)

---

## Behavioral Rules

- Prefer `stack` as the root in most cases
- Keep layouts shallow and readable
- Group logically related content inside `section`
- Always include an explicit action row (submit / cancel) for forms
- For display-only layouts, prefer combining text + table or text + card_list
- Use alert to draw attention to important information or next steps
- Use progress to show the user where they are in a multi-step flow
- Do not generate orphan components
- Do not generate unused components
- Do not exceed limits

---

## Goal

Produce a valid, complete, and structured UI tree that can be rendered without errors. For input collection, map directly to a validated workflow. For information display, present data clearly with visual hierarchy and logical grouping.
""")

        if idx >= len(descriptions):
            logger.warning(
                "Invalid tool description version %d, falling back to 0", idx
            )
            return descriptions[0]
        return descriptions[idx]

    # ------------------------------------------------------------------
    # Full description builders — one per version
    # ------------------------------------------------------------------

    def build_tool_description(self, version: int | None = None) -> str:
        """Build the compound widget tool description for the given version.

        Args:
            version: Description version (0=compact, 1=minimal, 2=verbose).
                Falls back to ``COMPOUND_WIDGET_TOOL_DESC_VERSION`` setting
                when *None*.

        """
        if version is None:
            from eylo.common.config import settings

            version = settings.COMPOUND_WIDGET_TOOL_DESC_VERSION
        builders = {
            0: self._build_description_v0,
            1: self._build_description_v1,
            2: self._build_description_v2,
        }
        builder = builders.get(version)
        if builder is None:
            logger.warning(
                "Unknown COMPOUND_WIDGET_TOOL_DESC_VERSION=%d, using v0", version
            )
            builder = self._build_description_v0
        return builder()

    def _build_description_v0(self) -> str:
        """V0 — Compact reference (~4800 chars).

        Leads with the required input format, compact component reference
        with props/rules, display-only components inline, constraints,
        and one full compound example.
        """
        sections: List[str] = [self.compile_descriptions(0)]

        # Compact interactive component reference
        for entry in self._catalog.values():
            props_schema = entry.json_schema.get("properties", {}).get("props", {})
            section = self._format_component_section(entry, props_schema)
            sections.append(section)

        # Display-only components — inline
        sections.append("")
        sections.append("## Display-Only Components (no user submissions)")
        sections.append("")
        sections.append(
            "**text** — Rich text/markdown block. "
            "Props: content (required): string; variant (optional): body|heading|caption|code"
        )
        sections.append(
            "**image** — Image display. "
            "Props: src (required): URL; alt (required): string; caption, width, height (optional)"
        )
        sections.append(
            "**progress** — Step indicator. "
            "Props: currentStep (required): number; totalSteps (required): number; "
            "label (optional); steps (optional): array of {label, status: pending|active|completed}"
        )
        sections.append(
            "**table** — Data table. "
            "Props: columns (required): array of {key, label, align?}; "
            "rows (required): array of objects; caption (optional)"
        )

        # Constraints
        sections.append("")
        sections.append("## Constraints")
        sections.append(
            f"Max {COMPOUND_MAX_COMPONENTS} components, max depth {COMPOUND_MAX_DEPTH}. "
            "All IDs unique. Only layout components have children. "
            "Must form a valid tree — no cycles, no orphans, exactly one root."
        )

        # One compact example
        sections.append("")
        sections.append("## Example")
        example = {
            "components": [
                {
                    "id": "root",
                    "component": "stack",
                    "props": {"spacing": "md"},
                    "children": ["info", "main_form"],
                },
                {
                    "id": "info",
                    "component": "alert",
                    "props": {
                        "severity": "info",
                        "message": "Please complete this form to continue.",
                    },
                },
                {
                    "id": "main_form",
                    "component": "form",
                    "props": {
                        "title": "Contact Information",
                        "fields": [
                            {
                                "type": "text",
                                "name": "name",
                                "label": "Your Name",
                                "required": True,
                            },
                            {
                                "type": "email",
                                "name": "email",
                                "label": "Email",
                                "required": True,
                            },
                        ],
                        "submitLabel": "Submit",
                    },
                },
            ],
            "root": "root",
        }
        sections.append(json.dumps(example, indent=2))

        return "\n".join(sections)

    def _build_description_v1(self) -> str:
        """V1 — Minimal schema-only (~3000 chars).

        Strips all prose. One line per component with required props only.
        For models that perform worse with longer tool descriptions.
        """
        sections: List[str] = [self.compile_descriptions(1)]

        # One-line per interactive component
        for entry in self._catalog.values():
            props_schema = entry.json_schema.get("properties", {}).get("props", {})
            required = props_schema.get("required", [])
            req_str = ", ".join(required) if required else "none"
            sections.append(
                f"- {entry.component}: {entry.description} Required props: {req_str}."
            )

        # Display components — single line each
        sections.append("")
        sections.append(
            "Display-only: text (content), image (src, alt), "
            "progress (currentStep, totalSteps), "
            "table (columns, rows)"
        )

        # Minimal example
        sections.append("")
        sections.append("Example:")
        sections.append(
            json.dumps(
                {
                    "components": [
                        {"id": "r", "component": "stack", "children": ["f"]},
                        {
                            "id": "f",
                            "component": "form",
                            "props": {
                                "title": "Contact",
                                "fields": [
                                    {"type": "text", "name": "name", "label": "Name"}
                                ],
                            },
                        },
                    ],
                    "root": "r",
                }
            )
        )

        return "\n".join(sections)

    def _build_description_v2(self) -> str:
        """V2 — Original verbose (~12500 chars).

        Full prose with use-case examples, composition patterns, behavioral
        rules, and per-component JSON examples.  This was the original
        description shipped before optimization.  Preserved as a baseline
        for A/B comparison.
        """
        sections: List[str] = [self.compile_descriptions(2)]

        # Verbose interactive component sections with when_to_use + examples
        sections.append("")
        sections.append("## Interactive Content Components")
        for entry in self._catalog.values():
            props_schema = entry.json_schema.get("properties", {}).get("props", {})
            section = self._format_component_section_verbose(entry, props_schema)
            sections.append("")
            sections.append(section)

        # Display-only components — verbose
        sections.append("")
        sections.append("## Display Components (display-only, no submissions)")
        sections.append("")
        sections.append('### component: "text"')
        sections.append("Rich text or markdown display block.")
        sections.append(
            "Props: content (required): string — text/markdown to display; "
            "variant (optional): one of body, heading, caption, code"
        )
        sections.append("")
        sections.append('### component: "image"')
        sections.append("Image display with optional caption.")
        sections.append(
            "Props: src (required): image URL; alt (required): accessible alt text; "
            "caption (optional): string; width (optional): number 1-2048; "
            "height (optional): number 1-2048"
        )
        sections.append("")
        sections.append('### component: "progress"')
        sections.append("Step progress indicator for multi-step flows.")
        sections.append(
            "Props: currentStep (required): number >= 1; "
            "totalSteps (required): number >= 1; "
            "label (optional): string; "
            "steps (optional): array of { label: string, "
            "status: pending|active|completed }. "
            "If steps is provided, its length must equal totalSteps."
        )
        sections.append("")
        sections.append('### component: "table"')
        sections.append("Data table with columns and rows.")
        sections.append(
            "Props: columns (required): array of { key: string, label: string, "
            'align?: "left"|"center"|"right" }; '
            "rows (required): array of objects where keys match column keys; "
            "caption (optional): string"
        )

        # Compound example
        sections.append("")
        sections.append("## Compound Example")
        example = {
            "components": [
                {
                    "id": "root",
                    "component": "stack",
                    "props": {"spacing": "md"},
                    "children": ["info", "main_form"],
                },
                {
                    "id": "info",
                    "component": "alert",
                    "props": {
                        "severity": "info",
                        "message": "Please complete this form to continue.",
                    },
                },
                {
                    "id": "main_form",
                    "component": "form",
                    "props": {
                        "title": "Contact Information",
                        "fields": [
                            {
                                "type": "text",
                                "name": "name",
                                "label": "Your Name",
                                "required": True,
                            },
                            {
                                "type": "email",
                                "name": "email",
                                "label": "Email",
                                "required": True,
                            },
                        ],
                        "submitLabel": "Submit",
                    },
                },
            ],
            "root": "root",
        }
        sections.append(json.dumps(example, indent=2))

        return "\n".join(sections)

    def _format_component_section_verbose(
        self,
        entry: WidgetCatalogEntry,
        props_schema: Dict[str, Any],
    ) -> str:
        """Original verbose component section format used by v2.

        Includes when_to_use, rules, required/optional props listing,
        prop details, and a full JSON example per component.
        """
        lines: List[str] = []
        lines.append(f'### component: "{entry.component}"')
        lines.append(entry.description)
        lines.append(f"When to use: {'; '.join(entry.when_to_use)}.")
        lines.append(f"Rules: {'; '.join(entry.rules)}.")

        required_props = props_schema.get("required", [])
        prop_defs = props_schema.get("properties", {})

        if required_props:
            lines.append(f"Required props: {', '.join(required_props)}.")

        optional_props = [k for k in prop_defs if k not in required_props]
        if optional_props:
            lines.append(f"Optional props: {', '.join(optional_props)}.")

        for prop_name, prop_def in prop_defs.items():
            detail = self._format_prop_detail(prop_name, prop_def)
            if detail:
                lines.append(detail)

        lines.append(f"Example: {json.dumps(entry.example_payload, sort_keys=True)}")
        return "\n".join(lines)

    def build_tool_input_schema(self) -> Dict[str, Any]:
        """Build Anthropic-compatible input schema for compound_render_widget.

        Uses a flat object with `components` array and `root` string —
        no top-level oneOf/allOf/anyOf.
        """
        return {
            "type": "object",
            "required": ["components", "root"],
            "additionalProperties": False,
            "properties": {
                "components": {
                    "type": "array",
                    "description": (
                        "Flat list of component nodes. "
                        "Each node has an id, component type, props, "
                        "and optional children (for layout components only)."
                    ),
                    "minItems": 1,
                    "maxItems": COMPOUND_MAX_COMPONENTS,
                    "items": {
                        "type": "object",
                        "required": ["id", "component", "props", "children"],
                        "additionalProperties": False,
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Unique identifier for this component.",
                            },
                            "component": {
                                "type": "string",
                                "enum": ALL_COMPOUND_COMPONENT_TYPES,
                                "description": "Component type.",
                            },
                            "props": {
                                "type": "string",
                                "description": (
                                    "JSON-serialized object of component-specific "
                                    "properties. Must be a valid JSON object string. "
                                    "See the tool description for each component's schema."
                                ),
                            },
                            "children": {
                                "type": ["array", "null"],
                                "items": {"type": "string"},
                                "description": (
                                    "Ordered child component IDs. "
                                    "Only layout components (stack, row, section) may have children. "
                                    "Use null for leaf components."
                                ),
                            },
                        },
                    },
                },
                "root": {
                    "type": "string",
                    "description": "ID of the root component.",
                },
            },
        }
