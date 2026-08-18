"""Application services for the `tools` domain."""

import inspect
import logging
from datetime import datetime, timezone
from types import FunctionType
from typing import Any, Callable
from uuid import UUID, uuid5

from pydantic import BaseModel, create_model
from slugify import slugify

from eylo.common.contracts.provider_config import Capability
from eylo.common.contracts.tool_availability import ToolRequirements
from eylo.common.schemas import CaseInSensitiveEnum
from eylo.modules.tools.schemas.platform import PlatformTool, PlatformToolInputSchema

logger = logging.getLogger(__name__)

# Fixed namespace for deterministic system tool UUIDs
SYSTEM_TOOL_NAMESPACE = UUID("11111111-1111-1111-1111-111111111111")


def system_tool_id(tool_name: str, organization_id: UUID) -> UUID:
    """Deterministic UUID for a system tool scoped to an organization."""
    return uuid5(SYSTEM_TOOL_NAMESPACE, f"{organization_id}:{tool_name}")


class ParamType(CaseInSensitiveEnum):
    """Optional. The type of the data."""

    TYPE_UNSPECIFIED = "TYPE_UNSPECIFIED"
    STRING = "STRING"
    NUMBER = "NUMBER"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"
    ARRAY = "ARRAY"
    OBJECT = "OBJECT"


_py_type_2_schema_type = {
    "str": ParamType.STRING,
    "int": ParamType.INTEGER,
    "float": ParamType.NUMBER,
    "bool": ParamType.BOOLEAN,
    "string": ParamType.STRING,
    "integer": ParamType.INTEGER,
    "number": ParamType.NUMBER,
    "boolean": ParamType.BOOLEAN,
    "list": ParamType.ARRAY,
    "array": ParamType.ARRAY,
    "tuple": ParamType.ARRAY,
    "object": ParamType.OBJECT,
    "Dict": ParamType.OBJECT,
    "List": ParamType.ARRAY,
    "Tuple": ParamType.ARRAY,
    "Any": ParamType.TYPE_UNSPECIFIED,
}


def _is_function(obj: Any) -> bool:
    """Check if the object is a function or a callable."""
    return isinstance(obj, FunctionType) or (
        inspect.isclass(obj) and issubclass(obj, FunctionType)
    )


def build_fn_declaration(func: Callable) -> type[BaseModel]:
    custom_schema_model = getattr(func, "__eylo_schema_model__", None)
    if custom_schema_model is not None:
        if inspect.isclass(custom_schema_model) and issubclass(
            custom_schema_model, BaseModel
        ):
            return custom_schema_model
        raise TypeError(
            f"Custom schema model for '{func.__name__}' must be a Pydantic BaseModel subclass."
        )

    signature = inspect.signature(func)
    # ctx: conversation context should be ignored
    ignore_params = ["self", "cls", "args", "kwargs", "ctx"]
    fields = {}
    for name, param in signature.parameters.items():
        if name in ignore_params:
            continue

        annotation = param.annotation if param.annotation is not inspect._empty else Any
        default = param.default if param.default is not inspect._empty else ...
        fields[name] = (annotation, default)

    _name = slugify(func.__name__, separator="_", lowercase=True)
    _mod = slugify(func.__module__, separator="_", lowercase=True)
    return create_model(f"{_mod}_{_name}_Schema", **fields)


class ToolRegistrationService:
    def __init__(self):
        self.registered_tools = {}
        self.registered_requirements: dict[str, ToolRequirements] = {}
        self.registered_provider_capabilities: dict[str, Capability | None] = {}

    # Registry entries are callables, not stateful tool classes.
    def register_tool(
        self,
        tool_name: str,
        tool_func: Callable,
        *,
        requirements: ToolRequirements | None = None,
        provider_capability: Capability | None = None,
    ):
        if not _is_function(tool_func):
            raise ValueError(f"Tool class '{tool_func}' is not a valid function.")
        declared_requirements = requirements or ToolRequirements()
        existing = self.registered_tools.get(tool_name)
        if existing is tool_func:
            if (
                self.registered_requirements[tool_name] != declared_requirements
                or self.registered_provider_capabilities[tool_name]
                is not provider_capability
            ):
                raise ValueError(
                    f"Tool '{tool_name}' was registered with different metadata."
                )
            return tool_func
        if existing is not None:
            raise ValueError(f"Tool '{tool_name}' is already registered.")
        self.registered_tools[tool_name] = tool_func
        self.registered_requirements[tool_name] = declared_requirements
        self.registered_provider_capabilities[tool_name] = provider_capability
        logger.debug(f"Tool '{tool_name}' registered successfully.")
        return tool_func

    def get_tool(self, tool_name: str):
        """Retrieve a registered tool by its name."""
        if tool_name not in self.registered_tools:
            raise ValueError(f"Tool '{tool_name}' is not registered.")
        return self.registered_tools[tool_name]

    def unregister_tool(self, tool_name: str):
        """Unregister a tool by its name."""
        self.get_tool(tool_name)
        del self.registered_tools[tool_name]
        del self.registered_requirements[tool_name]
        del self.registered_provider_capabilities[tool_name]
        logger.debug(f"Tool '{tool_name}' unregistered successfully.")
        return True

    def requirements_for(self, tool_name: str) -> ToolRequirements:
        """Return the code-owned availability contract for one system tool."""
        self.get_tool(tool_name)
        return self.registered_requirements[tool_name]

    def get_tool_schema(self, tool_name: str) -> type[BaseModel]:
        """Get the schema of a registered tool."""
        tool_func = self.get_tool(tool_name)
        return build_fn_declaration(tool_func)

    def get_llm_config(self, tool_name: str) -> dict:
        """Get the LLM config of a registered tool in platform-native format."""
        tool_schema = self.get_tool_schema(tool_name).model_json_schema(by_alias=True)

        return PlatformTool(
            name=tool_name,
            description=self.get_tool(tool_name).__doc__ or "",
            input_schema=PlatformToolInputSchema.model_validate(tool_schema),
        ).model_dump(by_alias=True, exclude_none=True)

    def list_catalog(
        self,
        organization_id: UUID,
        *,
        capabilities: set | None = None,
        provider_capability: Capability | None = None,
    ) -> list:
        """Return all registered tools as virtual ToolInDb objects for API discovery.

        Respects __eylo_feature_flag__ on tool functions — tools with a disabled
        flag are excluded from the catalog.

        Args:
            organization_id: Org to scope deterministic UUIDs to.

        Returns:
            List of ToolInDb-shaped objects (built via model_construct).

        """
        from eylo.common.config import settings
        from eylo.modules.tools.models import ToolKind
        from eylo.modules.tools.schemas.indb import ToolInDb

        tools = []
        now = datetime.now(timezone.utc)

        for tool_name, tool_func in self.registered_tools.items():
            if (
                provider_capability is not None
                and self.registered_provider_capabilities[tool_name]
                is not provider_capability
            ):
                continue
            if getattr(tool_func, "__eylo_catalog_hidden__", False):
                continue
            # Respect feature flag gating
            flag_name = getattr(tool_func, "__eylo_feature_flag__", None)
            if flag_name and not getattr(settings, flag_name, False):
                continue

            # A tool backed by infrastructure the organization has not
            # configured is not offered. Offering it would be worse than
            # withholding it: an agent given a memory tool by an organization
            # with no memory will use it, and whatever comes back becomes
            # something it says to a person.
            #
            # `capabilities` is passed in rather than looked up here, because
            # this method is synchronous and the answer is a database read.
            # None means "do not filter" — used where the caller genuinely
            # wants the whole catalog, such as documentation.
            requirements = self.requirements_for(tool_name)
            if capabilities is not None and not (
                requirements.organization_capabilities <= capabilities
            ):
                continue

            try:
                llm_config = self.get_llm_config(tool_name)
                platform_tool = PlatformTool.model_validate(llm_config)
            except Exception:
                logger.warning("Failed to build schema for system tool '%s'", tool_name)
                continue

            tools.append(
                ToolInDb.model_construct(
                    id=system_tool_id(tool_name, organization_id),
                    deleted=False,
                    created_at=now,
                    updated_at=now,
                    organization_id=organization_id,
                    name=tool_name,
                    slug=tool_name,
                    kind=ToolKind.SYSTEM,
                    display_name=tool_name.replace("_", " ").title(),
                    description=tool_func.__doc__ or "",
                    mcp_server_id=None,
                    llm_config=platform_tool,
                    executor_config={},
                )
            )

        return tools


local_tools_registry = ToolRegistrationService()
system_tools_registry = ToolRegistrationService()


def register_tool(tool_name: str | None = None) -> Callable:
    """Decorator to register a tool."""

    def decorator(func: Callable):
        if not _is_function(func):
            raise ValueError(f"'{func}' is not a valid function.")
        register_name = tool_name or func.__name__
        local_tools_registry.register_tool(register_name, func)
        return func

    return decorator


def register_local_tools():
    pass  # Add custom local tool registrations here


def register_system_tools():
    """Register module-owned tools under stable explicit slugs."""
    from eylo.common.contracts.tool_availability import (
        ToolRequirements,
        ToolRuntimeFact,
    )
    from eylo.modules.tools.services.executors.system_tools.compound_render_widget import (
        compound_render_widget,
    )
    from eylo.modules.tools.services.executors.system_tools.convert_to_utc import (
        convert_to_utc,
    )
    from eylo.modules.tools.services.executors.system_tools.get_current_time import (
        get_current_time,
    )
    from eylo.modules.tools.services.executors.system_tools.is_iso_datetime import (
        is_iso_datetime,
    )
    from eylo.modules.tools.services.executors.system_tools.schedule_tools import (
        schedule_cancel,
        schedule_create,
        schedule_list,
    )
    from eylo.modules.tools.services.executors.system_tools.send_email_tool import (
        send_email,
    )
    from eylo.modules.tools.services.executors.system_tools.set_agent_reminder import (
        set_agent_reminder,
    )

    registrations = (
        (
            "compound_render_widget",
            compound_render_widget,
            ToolRequirements(runtime_facts=frozenset({ToolRuntimeFact.WIDGET})),
            None,
        ),
        ("convert_to_utc", convert_to_utc, ToolRequirements(), None),
        ("get_current_time", get_current_time, ToolRequirements(), None),
        ("is_iso_datetime", is_iso_datetime, ToolRequirements(), None),
        ("schedule_cancel", schedule_cancel, ToolRequirements(), None),
        ("schedule_create", schedule_create, ToolRequirements(), None),
        ("schedule_list", schedule_list, ToolRequirements(), None),
        (
            "send_email",
            send_email,
            ToolRequirements(
                agent_capabilities=frozenset({Capability.EMAIL}),
                runtime_facts=frozenset({ToolRuntimeFact.DURABLE_EXECUTION}),
            ),
            Capability.EMAIL,
        ),
        ("set_agent_reminder", set_agent_reminder, ToolRequirements(), None),
    )
    for tool_name, tool_func, requirements, provider_capability in registrations:
        system_tools_registry.register_tool(
            tool_name,
            tool_func,
            requirements=requirements,
            provider_capability=provider_capability,
        )


register_local_tools()
register_system_tools()
