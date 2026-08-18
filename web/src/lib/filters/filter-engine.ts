import type {
  FilterAccessorValue,
  FilterCondition,
  FilterNode,
  FilterPrimitive,
  FilterSchema,
} from "./filter-types.ts";

function applyFilters<Item, Property extends string>(
  items: readonly Item[],
  filterTree: FilterNode<Property>,
  schema: FilterSchema<Item, Property, unknown>,
): Item[] {
  return items.filter((item) => matchesFilterNode(item, filterTree, schema));
}

function matchesFilterNode<Item, Property extends string>(
  item: Item,
  node: FilterNode<Property>,
  schema: FilterSchema<Item, Property, unknown>,
): boolean {
  if (node.type === "condition") {
    return matchesFilterCondition(item, node, schema);
  }

  const activeChildren = node.children.filter(hasFilterValues);
  if (activeChildren.length === 0) {
    return true;
  }

  return node.op === "and"
    ? activeChildren.every((child) => matchesFilterNode(item, child, schema))
    : activeChildren.some((child) => matchesFilterNode(item, child, schema));
}

function matchesFilterCondition<Item, Property extends string>(
  item: Item,
  condition: FilterCondition<Property>,
  schema: FilterSchema<Item, Property, unknown>,
): boolean {
  if (condition.values.length === 0) {
    return true;
  }

  const definition = schema.find(
    (candidate) => candidate.property === condition.property,
  );
  if (definition === undefined) {
    return false;
  }

  const actualValue = definition.accessor(item);
  if (condition.operator === "before" || condition.operator === "after") {
    return matchesDate(actualValue, condition.values[0], condition.operator);
  }

  const actualValues = toComparableValues(actualValue);
  const selectedValues = new Set(condition.values);
  const hasSelectedValue = actualValues.some((value) =>
    selectedValues.has(value),
  );

  switch (condition.operator) {
    case "is":
    case "is_any_of":
    case "includes_any":
      return hasSelectedValue;
    case "is_not":
    case "includes_none":
      return !hasSelectedValue;
    case "includes_all":
      return condition.values.every((value) => actualValues.includes(value));
  }
}

function matchesDate(
  actualValue: FilterAccessorValue,
  selectedValue: string | undefined,
  operator: "before" | "after",
): boolean {
  if (selectedValue === undefined) {
    return false;
  }

  const actualPrimitive = Array.isArray(actualValue)
    ? actualValue[0]
    : actualValue;
  const actualTime = toTime(actualPrimitive);
  const selectedTime = toTime(selectedValue);
  if (actualTime === null || selectedTime === null) {
    return false;
  }
  return operator === "before"
    ? actualTime < selectedTime
    : actualTime > selectedTime;
}

function toComparableValues(value: FilterAccessorValue): string[] {
  const values = Array.isArray(value) ? value : [value];
  return values
    .filter(
      (candidate): candidate is Exclude<FilterPrimitive, null | undefined> =>
        candidate !== null && candidate !== undefined,
    )
    .map((candidate) =>
      candidate instanceof Date ? candidate.toISOString() : String(candidate),
    );
}

function toTime(value: FilterPrimitive): number | null {
  if (value === null || value === undefined) {
    return null;
  }
  const time =
    value instanceof Date ? value.getTime() : Date.parse(String(value));
  return Number.isNaN(time) ? null : time;
}

function hasFilterValues<Property extends string>(
  node: FilterNode<Property>,
): boolean {
  return node.type === "condition"
    ? node.values.length > 0
    : node.children.some(hasFilterValues);
}

export { applyFilters };
