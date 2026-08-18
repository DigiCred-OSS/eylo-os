"""Data contracts for the `interfaces` domain."""

from typing import Annotated, Any, Dict, List, Literal, Optional, Set, Union

from pydantic import BaseModel, Field, field_validator, model_validator

_ALLOWED_URL_SCHEMES = ("http://", "https://", "/")


def _validate_safe_url(url: str) -> str:
    """Reject javascript:, data:, and other unsafe URL schemes."""
    if not any(url.startswith(scheme) for scheme in _ALLOWED_URL_SCHEMES):
        raise ValueError(
            f"URL must start with http://, https://, or /. Got: {url[:40]!r}"
        )
    return url


class WidgetOption(BaseModel):
    value: str
    label: str
    description: Optional[str] = None


class WidgetFieldValidation(BaseModel):
    min_length: Optional[int] = Field(default=None, alias="minLength")
    max_length: Optional[int] = Field(default=None, alias="maxLength")
    min: Optional[float] = None
    max: Optional[float] = None
    pattern: Optional[str] = None
    message: Optional[str] = None
    min_date: Optional[str] = Field(default=None, alias="minDate")
    max_date: Optional[str] = Field(default=None, alias="maxDate")


class WidgetFormField(BaseModel):
    type: Literal[
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
    ]
    name: str
    label: str
    placeholder: Optional[str] = None
    required: bool = False
    default_value: Optional[Any] = Field(default=None, alias="defaultValue")
    options: Optional[List[WidgetOption]] = None
    validation: Optional[WidgetFieldValidation] = None

    @model_validator(mode="after")
    def validate_options(self) -> "WidgetFormField":
        if self.type in {"select", "radio"} and not self.options:
            raise ValueError(f"{self.type} fields require at least one option")
        return self


class WidgetFormProps(BaseModel):
    title: str
    description: Optional[str] = None
    fields: List[WidgetFormField] = Field(min_length=1)
    submit_label: Optional[str] = Field(default=None, alias="submitLabel")
    cancel_label: Optional[str] = Field(default=None, alias="cancelLabel")

    @model_validator(mode="after")
    def validate_unique_field_names(self) -> "WidgetFormProps":
        field_names = [field.name for field in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError("form field names must be unique")
        return self


class WidgetButton(BaseModel):
    value: str
    label: str
    variant: Optional[
        Literal["primary", "secondary", "destructive", "ghost", "outline", "link"]
    ] = None
    icon: Optional[str] = None


class WidgetButtonGroupProps(BaseModel):
    question: Optional[str] = None
    layout: Optional[Literal["horizontal", "vertical"]] = None
    buttons: List[WidgetButton] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_values(self) -> "WidgetButtonGroupProps":
        values = [button.value for button in self.buttons]
        if len(values) != len(set(values)):
            raise ValueError("button values must be unique")
        return self


class WidgetCard(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    image: Optional[str] = None
    price: Optional[str] = None
    badge: Optional[str] = None
    features: Optional[List[str]] = None

    @field_validator("image")
    @classmethod
    def validate_image_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_safe_url(v)
        return v


class WidgetCardListProps(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    selection_mode: Optional[Literal["single", "multiple"]] = Field(
        default=None, alias="selectionMode"
    )
    submit_label: Optional[str] = Field(default=None, alias="submitLabel")
    cards: List[WidgetCard] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "WidgetCardListProps":
        ids = [card.id for card in self.cards]
        if len(ids) != len(set(ids)):
            raise ValueError("card ids must be unique")
        return self


class WidgetDatePickerValidation(BaseModel):
    min_date: Optional[str] = Field(default=None, alias="minDate")
    max_date: Optional[str] = Field(default=None, alias="maxDate")
    message: Optional[str] = None


class WidgetDatePickerProps(BaseModel):
    label: str
    name: str
    description: Optional[str] = None
    mode: Optional[Literal["date", "time", "datetime"]] = None
    placeholder: Optional[str] = None
    required: bool = False
    default_value: Optional[str] = Field(default=None, alias="defaultValue")
    submit_label: Optional[str] = Field(default=None, alias="submitLabel")
    validation: Optional[WidgetDatePickerValidation] = None

    @model_validator(mode="after")
    def validate_time_default(self) -> "WidgetDatePickerProps":
        if self.mode == "time" and self.default_value:
            parts = self.default_value.split(":")
            if len(parts) != 2 or not all(part.isdigit() for part in parts):
                raise ValueError('time defaultValue must use the "HH:MM" format')
            hours, minutes = int(parts[0]), int(parts[1])
            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                raise ValueError(
                    "time defaultValue out of range: hours must be 0-23, minutes 0-59"
                )
        return self


class WidgetAlertProps(BaseModel):
    title: Optional[str] = None
    message: str
    dismissible: bool = False
    severity: Optional[Literal["info", "success", "warning", "error"]] = None


class WidgetTextProps(BaseModel):
    content: str = Field(..., description="Text or markdown content to display.")
    variant: Optional[Literal["body", "heading", "caption", "code"]] = None


class WidgetImageProps(BaseModel):
    src: str = Field(..., description="Image URL.")
    alt: str = Field(..., description="Accessible alt text.")
    caption: Optional[str] = None
    width: Optional[int] = Field(default=None, ge=1, le=2048)
    height: Optional[int] = Field(default=None, ge=1, le=2048)

    @field_validator("src")
    @classmethod
    def validate_src_url(cls, v: str) -> str:
        return _validate_safe_url(v)


class WidgetProgressStep(BaseModel):
    label: str
    status: Literal["pending", "active", "completed"] = "pending"


class WidgetProgressProps(BaseModel):
    current_step: int = Field(..., alias="currentStep", ge=1)
    total_steps: int = Field(..., alias="totalSteps", ge=1)
    label: Optional[str] = None
    steps: Optional[List[WidgetProgressStep]] = None

    @model_validator(mode="after")
    def validate_steps(self) -> "WidgetProgressProps":
        if self.current_step > self.total_steps:
            raise ValueError("currentStep cannot exceed totalSteps")
        if self.steps and len(self.steps) != self.total_steps:
            raise ValueError("steps array length must equal totalSteps")
        return self


class WidgetTableColumn(BaseModel):
    key: str
    label: str
    align: Optional[Literal["left", "center", "right"]] = None

    @field_validator("align", mode="before")
    @classmethod
    def normalize_align(cls, v: Any) -> Any:
        """Accept CSS-style start/end as aliases for left/right."""
        if v == "start":
            return "left"
        if v == "end":
            return "right"
        return v


class WidgetTableProps(BaseModel):
    columns: List[WidgetTableColumn] = Field(..., min_length=1)
    rows: List[Dict[str, Any]] = Field(..., min_length=1)
    caption: Optional[str] = None


class WidgetFormPayload(BaseModel):
    component: Literal["form"]
    props: WidgetFormProps


class WidgetButtonGroupPayload(BaseModel):
    component: Literal["button_group"]
    props: WidgetButtonGroupProps


class WidgetCardListPayload(BaseModel):
    component: Literal["card_list"]
    props: WidgetCardListProps


class WidgetDatePickerPayload(BaseModel):
    component: Literal["date_picker"]
    props: WidgetDatePickerProps


class WidgetAlertPayload(BaseModel):
    component: Literal["alert"]
    props: WidgetAlertProps


class WidgetTextPayload(BaseModel):
    component: Literal["text"]
    props: WidgetTextProps


class WidgetImagePayload(BaseModel):
    component: Literal["image"]
    props: WidgetImageProps


class WidgetProgressPayload(BaseModel):
    component: Literal["progress"]
    props: WidgetProgressProps


class WidgetTablePayload(BaseModel):
    component: Literal["table"]
    props: WidgetTableProps


WidgetComponentPayload = Annotated[
    Union[
        WidgetFormPayload,
        WidgetButtonGroupPayload,
        WidgetCardListPayload,
        WidgetDatePickerPayload,
        WidgetAlertPayload,
        WidgetTextPayload,
        WidgetImagePayload,
        WidgetProgressPayload,
        WidgetTablePayload,
    ],
    Field(discriminator="component"),
]


class WidgetCatalogEntry(BaseModel):
    component: str
    version: str
    status: Literal["active", "deferred"]
    description: str
    json_schema: Dict[str, Any] = Field(alias="schema")
    when_to_use: List[str]
    required_props: List[str]
    rules: List[str]
    example_payload: Dict[str, Any]


# ====================== Layout Components ======================
# Structural-only components for compound widget composition.
# They compose children but produce no interactive submissions.


LAYOUT_COMPONENT_TYPES = {"stack", "row", "section", "divider"}

SPACING_VALUES = ("xs", "sm", "md", "lg", "xl")
ALIGN_VALUES = ("start", "center", "end", "stretch")


class WidgetDividerProps(BaseModel):
    label: Optional[str] = None


class WidgetStackProps(BaseModel):
    spacing: Optional[Literal["xs", "sm", "md", "lg", "xl"]] = None


class WidgetRowProps(BaseModel):
    spacing: Optional[Literal["xs", "sm", "md", "lg", "xl"]] = None
    align: Optional[Literal["start", "center", "end", "stretch"]] = None


class WidgetSectionProps(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    collapsible: bool = False


# ====================== Compound Widget Schemas ======================
# Flat adjacency-list model: each component has an ID, layout components
# reference children by ID. Inspired by A2UI (Google).

# All component types recognized in compound payloads.
ALL_COMPOUND_COMPONENT_TYPES = sorted(
    {
        "form",
        "button_group",
        "card_list",
        "date_picker",
        "alert",
        "text",
        "image",
        "progress",
        "table",
    }
    | LAYOUT_COMPONENT_TYPES
)

COMPOUND_MAX_DEPTH = 3
COMPOUND_MAX_COMPONENTS = 15


class CompoundWidgetNode(BaseModel):
    """A single node in the compound widget adjacency list."""

    id: str = Field(
        ...,
        description="Unique identifier for this component within the compound widget.",
    )
    component: str = Field(
        ...,
        description="Component type (layout or content).",
    )
    props: Dict[str, Any] = Field(
        default_factory=dict,
        description="Component-specific properties.",
    )
    children: Optional[List[str]] = Field(
        default=None,
        description="Ordered list of child component IDs (layout components only).",
    )

    @field_validator("props", mode="before")
    @classmethod
    def _parse_props_string(cls, v: Any) -> Dict[str, Any]:
        """Accept both JSON strings (from strict-mode LLM output) and dicts."""
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
            except (json.JSONDecodeError, TypeError) as exc:
                raise ValueError(f"props must be a valid JSON object string: {exc}")
            if not isinstance(parsed, dict):
                raise ValueError(
                    f"props JSON must decode to an object, got {type(parsed).__name__}"
                )
            return parsed
        return v


class CompoundWidgetPayload(BaseModel):
    """Top-level compound widget payload — adjacency-list model."""

    components: List[CompoundWidgetNode] = Field(
        ...,
        min_length=1,
        max_length=COMPOUND_MAX_COMPONENTS,
        description="Flat list of components with ID-based relationships.",
    )
    root: str = Field(
        ...,
        description="ID of the root component that anchors the tree.",
    )

    @model_validator(mode="after")
    def validate_compound_tree(self) -> "CompoundWidgetPayload":
        """Validate structural integrity of the compound widget tree."""
        ids = [node.id for node in self.components]
        id_set = set(ids)

        # Unique IDs
        if len(ids) != len(id_set):
            seen: Set[str] = set()
            dupes = [nid for nid in ids if nid in seen or seen.add(nid)]  # type: ignore[func-returns-value]
            raise ValueError(f"Duplicate component IDs: {dupes}")

        # Root exists
        if self.root not in id_set:
            raise ValueError(
                f"Root '{self.root}' does not match any component ID. "
                f"Available IDs: {sorted(id_set)}"
            )

        # Build lookup
        node_map = {node.id: node for node in self.components}

        # Only layout components may have children
        for node in self.components:
            if (
                node.children is not None
                and node.component not in LAYOUT_COMPONENT_TYPES
            ):
                raise ValueError(
                    f"Component '{node.id}' (type '{node.component}') "
                    f"cannot have children — only layout components "
                    f"({', '.join(sorted(LAYOUT_COMPONENT_TYPES))}) support children."
                )

        # All child references must point to existing IDs
        for node in self.components:
            for child_id in node.children or []:
                if child_id not in id_set:
                    raise ValueError(
                        f"Component '{node.id}' references unknown child '{child_id}'. "
                        f"Available IDs: {sorted(id_set)}"
                    )

        # Detect cycles via DFS
        visited: Set[str] = set()
        in_stack: Set[str] = set()

        def _dfs(nid: str) -> None:
            if nid in in_stack:
                raise ValueError(f"Cycle detected involving component '{nid}'.")
            if nid in visited:
                return
            in_stack.add(nid)
            for child_id in node_map[nid].children or []:
                _dfs(child_id)
            in_stack.discard(nid)
            visited.add(nid)

        _dfs(self.root)

        # Detect orphans (nodes unreachable from root)
        orphans = id_set - visited
        if orphans:
            raise ValueError(
                f"Orphan components not reachable from root '{self.root}': "
                f"{sorted(orphans)}"
            )

        # Max depth check
        def _depth(nid: str) -> int:
            children = node_map[nid].children or []
            if not children:
                return 1
            return 1 + max(_depth(c) for c in children)

        depth = _depth(self.root)
        if depth > COMPOUND_MAX_DEPTH:
            raise ValueError(
                f"Compound widget tree depth is {depth}, "
                f"exceeds maximum of {COMPOUND_MAX_DEPTH}."
            )

        return self
