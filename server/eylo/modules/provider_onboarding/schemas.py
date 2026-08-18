"""Public response contract for provider onboarding metadata."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from eylo.modules.provider_configs.constants import Capability


class ProviderFieldOption(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str
    label: str


class ProviderFieldCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    equals: str | bool


class ProviderFieldDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    wire_key: str
    label: str
    description: str | None = None
    kind: Literal[
        "text",
        "password",
        "integer",
        "number",
        "boolean",
        "select",
        "string_list",
        "provider_config",
    ]
    target: Literal["config", "secrets"] = "config"
    required: bool = False
    secret: bool = False
    multiline: bool = False
    options: tuple[ProviderFieldOption, ...] = ()
    allow_custom: bool = False
    minimum: float | None = None
    maximum: float | None = None
    visible_when: ProviderFieldCondition | None = None
    required_when: ProviderFieldCondition | None = None
    reference_capability: Capability | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> "ProviderFieldDefinition":
        if self.secret != (self.target == "secrets"):
            raise ValueError("Secret fields must target secrets and only secrets.")
        if self.kind == "password" and not self.secret:
            raise ValueError("Password fields must be secret fields.")
        if self.kind == "select" and not self.options:
            raise ValueError("Select fields must publish at least one option.")
        if self.kind != "select" and self.options:
            raise ValueError("Only select fields may publish static options.")
        if self.allow_custom and self.kind != "select":
            raise ValueError("Only select fields may allow a custom value.")
        if self.kind == "provider_config" and self.reference_capability is None:
            raise ValueError(
                "Provider-config fields must name their referenced capability."
            )
        if self.kind != "provider_config" and self.reference_capability is not None:
            raise ValueError(
                "Only provider-config fields may name a referenced capability."
            )
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError("Field minimum cannot exceed maximum.")
        return self


class ProviderDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    label: str
    description: str | None = None
    fields: tuple[ProviderFieldDefinition, ...]
    require_one_of: tuple[tuple[str, ...], ...] = ()

    @model_validator(mode="after")
    def validate_field_references(self) -> "ProviderDefinition":
        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Provider {self.id} publishes duplicate field keys.")
        known_keys = set(keys)
        for group in self.require_one_of:
            if len(group) < 2 or not set(group).issubset(known_keys):
                raise ValueError(
                    f"Provider {self.id} has an invalid require-one-of group."
                )
        for field in self.fields:
            for condition in (field.visible_when, field.required_when):
                if condition is not None and condition.field not in known_keys:
                    raise ValueError(
                        f"Provider {self.id} field {field.key} references an "
                        "unknown condition field."
                    )
        return self


class CapabilityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: Capability
    label: str
    description: str
    configure_via: str
    providers: tuple[ProviderDefinition, ...]

    @model_validator(mode="after")
    def validate_providers(self) -> "CapabilityDefinition":
        provider_ids = [provider.id for provider in self.providers]
        if not provider_ids:
            raise ValueError(f"Capability {self.capability.value} has no providers.")
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError(
                f"Capability {self.capability.value} publishes duplicate providers."
            )
        return self


class ProviderOnboardingCatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capabilities: tuple[CapabilityDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_capabilities(self) -> "ProviderOnboardingCatalogResponse":
        capabilities = [definition.capability for definition in self.capabilities]
        if len(capabilities) != len(set(capabilities)):
            raise ValueError("Provider onboarding publishes duplicate capabilities.")
        missing = set(Capability) - set(capabilities)
        extra = set(capabilities) - set(Capability)
        if missing or extra:
            raise ValueError(
                "Provider onboarding must publish every capability exactly once: "
                f"missing={sorted(item.value for item in missing)}, "
                f"extra={sorted(item.value for item in extra)}"
            )
        return self


__all__ = [
    "CapabilityDefinition",
    "ProviderDefinition",
    "ProviderFieldCondition",
    "ProviderFieldDefinition",
    "ProviderFieldOption",
    "ProviderOnboardingCatalogResponse",
]
