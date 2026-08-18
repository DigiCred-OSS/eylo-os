import type {
  TCompoundWidgetNode,
  TCompoundWidgetPayload,
  TRegisteredWidgetComponent,
  TWidgetComponentType,
  TWidgetPayloadEnvelope,
  TWidgetSchema,
  TWidgetValidationIssue,
  TWidgetValidationResult,
} from "./types";
import { isRecord } from "@eylo/utils/type-guards";

const widgetComponentRegistry = new Map<TWidgetComponentType, TRegisteredWidgetComponent>();

const appendPath = (path: string, next: string): string => `${path}.${next}`;

const validateSchemaDefinition = (
  schema: unknown,
  path = "$.schema"
): TWidgetValidationIssue[] => {
  if (!isRecord(schema)) {
    return [{ path, message: "Schema definition must be an object." }];
  }

  const { type } = schema;
  if (typeof type !== "string") {
    return [{ path: appendPath(path, "type"), message: "Schema type is required." }];
  }

  switch (type) {
    case "string":
    case "number":
    case "boolean":
    case "any":
      return [];

    case "array": {
      if (!("items" in schema)) {
        return [{ path: appendPath(path, "items"), message: "Array schemas require an items definition." }];
      }

      return validateSchemaDefinition(schema.items, appendPath(path, "items"));
    }

    case "object": {
      const properties = schema.properties;
      if (!isRecord(properties)) {
        return [
          {
            path: appendPath(path, "properties"),
            message: "Object schemas require a properties object.",
          },
        ];
      }

      return Object.entries(properties).flatMap(([key, propertySchema]) =>
        validateSchemaDefinition(propertySchema, appendPath(appendPath(path, "properties"), key))
      );
    }

    default:
      return [{ path: appendPath(path, "type"), message: `Unsupported schema type "${type}".` }];
  }
};

const validateRegisteredComponentDefinition = (
  definition: TRegisteredWidgetComponent
): TWidgetValidationIssue[] => {
  const issues: TWidgetValidationIssue[] = [];

  if (typeof definition.type !== "string" || definition.type.trim().length === 0) {
    issues.push({
      path: "$.type",
      message: "Registered components must define a non-empty type.",
    });
  }

  if (typeof definition.version !== "string" || definition.version.trim().length === 0) {
    issues.push({
      path: "$.version",
      message: "Registered components must define a version string.",
    });
  }

  if (definition.status !== "active" && definition.status !== "deferred") {
    issues.push({
      path: "$.status",
      message: 'Registered components must use "active" or "deferred" status.',
    });
  }

  issues.push(...validateSchemaDefinition(definition.schema));
  return issues;
};

const validateSchemaValue = (
  schema: TWidgetSchema,
  value: unknown,
  path = "$"
): TWidgetValidationIssue[] => {
  if (value === undefined || value === null) {
    return schema.optional ? [] : [{ path, message: "Value is required." }];
  }

  switch (schema.type) {
    case "string": {
      if (typeof value !== "string") {
        return [{ path, message: "Expected a string." }];
      }

      const issues: TWidgetValidationIssue[] = [];

      if (schema.enum && !schema.enum.includes(value)) {
        issues.push({
          path,
          message: `Expected one of: ${schema.enum.join(", ")}.`,
        });
      }
      if (schema.minLength !== undefined && value.length < schema.minLength) {
        issues.push({
          path,
          message: `Must be at least ${schema.minLength} characters.`,
        });
      }
      if (schema.maxLength !== undefined && value.length > schema.maxLength) {
        issues.push({
          path,
          message: `Must be at most ${schema.maxLength} characters.`,
        });
      }
      if (schema.pattern) {
        try {
          const regex = new RegExp(schema.pattern);
          if (!regex.test(value)) {
            issues.push({ path, message: "Value does not match the required pattern." });
          }
        } catch {
          issues.push({ path, message: "Invalid validation pattern in schema." });
        }
      }
      return issues;
    }

    case "number": {
      if (typeof value !== "number" || Number.isNaN(value)) {
        return [{ path, message: "Expected a number." }];
      }

      const issues: TWidgetValidationIssue[] = [];
      if (schema.min !== undefined && value < schema.min) {
        issues.push({ path, message: `Must be greater than or equal to ${schema.min}.` });
      }
      if (schema.max !== undefined && value > schema.max) {
        issues.push({ path, message: `Must be less than or equal to ${schema.max}.` });
      }
      return issues;
    }

    case "boolean": {
      if (typeof value !== "boolean") {
        return [{ path, message: "Expected a boolean." }];
      }
      return [];
    }

    case "any": {
      return [];
    }

    case "array": {
      if (!Array.isArray(value)) {
        return [{ path, message: "Expected an array." }];
      }

      const issues: TWidgetValidationIssue[] = [];
      if (schema.minItems !== undefined && value.length < schema.minItems) {
        issues.push({ path, message: `Must have at least ${schema.minItems} items.` });
      }
      if (schema.maxItems !== undefined && value.length > schema.maxItems) {
        issues.push({ path, message: `Must have at most ${schema.maxItems} items.` });
      }

      value.forEach((item, index) => {
        issues.push(...validateSchemaValue(schema.items, item, `${path}[${index}]`));
      });

      return issues;
    }

    case "object": {
      if (!isRecord(value)) {
        return [{ path, message: "Expected an object." }];
      }

      const issues: TWidgetValidationIssue[] = [];
      const requiredKeys = schema.required ?? [];

      for (const key of requiredKeys) {
        if (!(key in value)) {
          issues.push({ path: appendPath(path, key), message: "Property is required." });
        }
      }

      for (const [key, propertySchema] of Object.entries(schema.properties)) {
        if (key in value) {
          issues.push(...validateSchemaValue(propertySchema, value[key], appendPath(path, key)));
        }
      }

      if (schema.additionalProperties === false) {
        for (const key of Object.keys(value)) {
          if (!(key in schema.properties)) {
            issues.push({
              path: appendPath(path, key),
              message: "Unknown property.",
            });
          }
        }
      }

      return issues;
    }
  }
};

export const validateWidgetComponentDefinition = (
  definition: TRegisteredWidgetComponent
): TWidgetValidationResult<TRegisteredWidgetComponent> => {
  const issues = validateRegisteredComponentDefinition(definition);

  if (issues.length > 0) {
    return {
      ok: false,
      issues,
    };
  }

  return {
    ok: true,
    value: definition,
    issues: [],
  };
};

export const registerWidgetComponent = (definition: TRegisteredWidgetComponent): void => {
  const validation = validateWidgetComponentDefinition(definition);

  if (!validation.ok) {
    throw new Error(
      `Invalid widget component registration for "${definition.type}": ${validation.issues
        .map((issue) => `${issue.path} ${issue.message}`)
        .join("; ")}`
    );
  }
  widgetComponentRegistry.set(definition.type, definition);
};

export const registerWidgetComponents = (
  definitions: readonly TRegisteredWidgetComponent[]
): void => {
  definitions.forEach((definition) => {
    registerWidgetComponent(definition);
  });
};

export const getRegisteredWidgetComponents = (): TRegisteredWidgetComponent[] => {
  return Array.from(widgetComponentRegistry.values());
};

export const getActiveWidgetComponents = (): TRegisteredWidgetComponent[] => {
  return getRegisteredWidgetComponents().filter((definition) => definition.status === "active");
};

export const getRegisteredWidgetComponent = (
  type: string
): TRegisteredWidgetComponent | undefined => {
  return widgetComponentRegistry.get(type);
};

export const getWidgetComponentSchema = (type: string): TWidgetSchema | undefined => {
  return getRegisteredWidgetComponent(type)?.schema;
};

export const clearWidgetComponentRegistry = (): void => {
  widgetComponentRegistry.clear();
};

export const validateWidgetPayload = (
  payload: unknown
): TWidgetValidationResult<TWidgetPayloadEnvelope> => {
  if (!isRecord(payload)) {
    return {
      ok: false,
      issues: [{ path: "$", message: "Widget payload must be an object." }],
    };
  }

  const component = payload.component;
  if (typeof component !== "string" || component.trim().length === 0) {
    return {
      ok: false,
      issues: [{ path: "$.component", message: "Component type is required." }],
    };
  }

  const definition = getRegisteredWidgetComponent(component);
  if (!definition) {
    return {
      ok: false,
      issues: [{ path: "$.component", message: `Component "${component}" is not registered.` }],
    };
  }

  if (definition.status !== "active") {
    return {
      ok: false,
      issues: [{ path: "$.component", message: `Component "${component}" is not active.` }],
    };
  }

  const schemaIssues = validateSchemaValue(definition.schema, payload);
  if (schemaIssues.length > 0) {
    return { ok: false, issues: schemaIssues };
  }

  const semanticIssues = definition.validatePayload
    ? definition.validatePayload(payload as TWidgetPayloadEnvelope)
    : [];

  if (semanticIssues.length > 0) {
    return { ok: false, issues: semanticIssues };
  }

  return {
    ok: true,
    value: payload as TWidgetPayloadEnvelope,
    issues: [],
  };
};

const LAYOUT_COMPONENT_TYPES = new Set(["stack", "row", "section"]);
const COMPOUND_MAX_DEPTH = 3;
const COMPOUND_MAX_COMPONENTS = 15;

/**
 * Validate a compound widget payload (adjacency-list model).
 *
 * Checks: structure, unique IDs, root existence, no cycles, no orphans,
 * depth limit, children only on layout components, and per-node schema validation.
 */
export const validateCompoundWidgetPayload = (
  payload: unknown
): TWidgetValidationResult<TCompoundWidgetPayload> => {
  if (!isRecord(payload)) {
    return { ok: false, issues: [{ path: "$", message: "Compound payload must be an object." }] };
  }

  const components = payload.components;
  const root = payload.root;

  if (!Array.isArray(components) || components.length === 0) {
    return { ok: false, issues: [{ path: "$.components", message: "Components array is required and must not be empty." }] };
  }

  if (typeof root !== "string" || root.trim().length === 0) {
    return { ok: false, issues: [{ path: "$.root", message: "Root component ID is required." }] };
  }

  if (components.length > COMPOUND_MAX_COMPONENTS) {
    return {
      ok: false,
      issues: [{ path: "$.components", message: `Too many components (${components.length}). Maximum is ${COMPOUND_MAX_COMPONENTS}.` }],
    };
  }

  const issues: TWidgetValidationIssue[] = [];
  const nodeMap = new Map<string, TCompoundWidgetNode>();

  // Parse and validate each node's basic structure
  for (let i = 0; i < components.length; i++) {
    const node = components[i];
    if (!isRecord(node)) {
      issues.push({ path: `$.components[${i}]`, message: "Each component must be an object." });
      continue;
    }

    const id = node.id;
    const component = node.component;

    if (typeof id !== "string" || id.trim().length === 0) {
      issues.push({ path: `$.components[${i}].id`, message: "Component ID is required." });
      continue;
    }
    if (typeof component !== "string" || component.trim().length === 0) {
      issues.push({ path: `$.components[${i}].component`, message: "Component type is required." });
      continue;
    }

    if (nodeMap.has(id)) {
      issues.push({ path: `$.components[${i}].id`, message: `Duplicate component ID "${id}".` });
      continue;
    }

    const children = Array.isArray(node.children) ? (node.children as string[]) : undefined;
    const props = isRecord(node.props) ? (node.props as Record<string, unknown>) : {};

    nodeMap.set(id, { id, component, props, children });
  }

  if (issues.length > 0) {
    return { ok: false, issues };
  }

  // Root must exist
  if (!nodeMap.has(root)) {
    return { ok: false, issues: [{ path: "$.root", message: `Root "${root}" does not match any component ID.` }] };
  }

  // Only layout components may have children
  // Also enforce tree structure: each child may have at most one parent
  const childToParent = new Map<string, string>();
  for (const [, node] of nodeMap) {
    if (node.children && !LAYOUT_COMPONENT_TYPES.has(node.component)) {
      issues.push({
        path: `$.components[${node.id}].children`,
        message: `Component "${node.id}" (type "${node.component}") cannot have children — only layout components support children.`,
      });
    }
    // All child references must exist and each child must have exactly one parent
    for (const childId of node.children ?? []) {
      if (!nodeMap.has(childId)) {
        issues.push({
          path: `$.components[${node.id}].children`,
          message: `Component "${node.id}" references unknown child "${childId}".`,
        });
      } else {
        const existingParent = childToParent.get(childId);
        if (existingParent) {
          issues.push({
            path: `$.components[${node.id}].children`,
            message: `Component "${childId}" has multiple parents: "${existingParent}" and "${node.id}". Each component must have exactly one parent.`,
          });
        } else {
          childToParent.set(childId, node.id);
        }
      }
    }
  }

  if (issues.length > 0) {
    return { ok: false, issues };
  }

  // Cycle detection + reachability (DFS from root)
  const visited = new Set<string>();
  const inStack = new Set<string>();

  const dfs = (id: string): boolean => {
    if (inStack.has(id)) {
      issues.push({ path: `$.components[${id}]`, message: `Cycle detected involving component "${id}".` });
      return false;
    }
    if (visited.has(id)) return true;
    inStack.add(id);
    const node = nodeMap.get(id)!;
    for (const childId of node.children ?? []) {
      if (!dfs(childId)) return false;
    }
    inStack.delete(id);
    visited.add(id);
    return true;
  };

  if (!dfs(root)) {
    return { ok: false, issues };
  }

  // Orphan detection
  const orphans = [...nodeMap.keys()].filter((id) => !visited.has(id));
  if (orphans.length > 0) {
    issues.push({ path: "$.components", message: `Orphan components not reachable from root: ${orphans.join(", ")}.` });
    return { ok: false, issues };
  }

  // Depth check
  const depth = (id: string): number => {
    const node = nodeMap.get(id)!;
    const children = node.children ?? [];
    if (children.length === 0) return 1;
    return 1 + Math.max(...children.map(depth));
  };

  const treeDepth = depth(root);
  if (treeDepth > COMPOUND_MAX_DEPTH) {
    return {
      ok: false,
      issues: [{ path: "$.components", message: `Tree depth ${treeDepth} exceeds maximum of ${COMPOUND_MAX_DEPTH}.` }],
    };
  }

  // Per-node component validation (schema + semantic)
  for (const [, node] of nodeMap) {
    const nodePayload = { component: node.component, props: node.props };
    const nodeResult = validateWidgetPayload(nodePayload);
    if (!nodeResult.ok) {
      for (const issue of nodeResult.issues) {
        issues.push({
          path: `$.components[${node.id}].${issue.path.replace("$.", "")}`,
          message: issue.message,
        });
      }
    }
  }

  if (issues.length > 0) {
    return { ok: false, issues };
  }

  return {
    ok: true,
    value: { components: [...nodeMap.values()], root } as TCompoundWidgetPayload,
    issues: [],
  };
};
