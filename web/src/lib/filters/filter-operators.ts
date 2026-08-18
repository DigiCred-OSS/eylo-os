import type {
  FilterDefinition,
  FilterOperator,
  FilterValueType,
} from "./filter-types.ts";

const DEFAULT_OPERATORS: Record<FilterValueType, readonly FilterOperator[]> = {
  "single-select": ["is", "is_not"],
  "multi-select": ["is", "is_not"],
  date: ["before", "after"],
  labels: ["includes_any", "includes_all", "includes_none"],
  links: ["includes_any", "includes_all", "includes_none"],
};

const DEFAULT_OPERATOR: Record<FilterValueType, FilterOperator> = {
  "single-select": "is",
  "multi-select": "is",
  date: "before",
  labels: "includes_any",
  links: "includes_any",
};

function getFilterOperators<Item, Property extends string, Icon>(
  definition: FilterDefinition<Item, Property, Icon>,
  valueCount: number,
): readonly FilterOperator[] {
  const configured =
    definition.operators ?? DEFAULT_OPERATORS[definition.valueType];
  const normalized = configured.map((operator) =>
    normalizeFilterOperator(operator, definition.valueType, valueCount),
  );
  return [...new Set(normalized)];
}

function getDefaultFilterOperator(valueType: FilterValueType): FilterOperator {
  return DEFAULT_OPERATOR[valueType];
}

function normalizeFilterOperator(
  operator: FilterOperator,
  valueType: FilterValueType,
  valueCount: number,
): FilterOperator {
  if (valueType !== "multi-select") {
    return operator;
  }
  if (operator === "is" && valueCount > 1) {
    return "is_any_of";
  }
  if (operator === "is_any_of" && valueCount <= 1) {
    return "is";
  }
  return operator;
}

function getFilterOperatorLabel(
  operator: FilterOperator,
  valueCount: number,
): string {
  switch (operator) {
    case "is":
      return "is";
    case "is_not":
      return "is not";
    case "is_any_of":
      return "is either of";
    case "includes_any":
      return valueCount === 2 ? "includes either" : "includes any";
    case "includes_all":
      return "includes all";
    case "includes_none":
      return valueCount === 2 ? "includes neither" : "includes none";
    case "before":
      return "before";
    case "after":
      return "after";
  }
}

export {
  getDefaultFilterOperator,
  getFilterOperatorLabel,
  getFilterOperators,
  normalizeFilterOperator,
};
