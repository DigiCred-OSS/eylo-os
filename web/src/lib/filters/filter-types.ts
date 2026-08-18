type FilterGroupOperator = "and" | "or";

type FilterValueType =
  "single-select" | "multi-select" | "date" | "labels" | "links";

type FilterOperator =
  | "is"
  | "is_not"
  | "is_any_of"
  | "includes_any"
  | "includes_all"
  | "includes_none"
  | "before"
  | "after";

type FilterPrimitive = string | number | boolean | Date | null | undefined;
type FilterAccessorValue = FilterPrimitive | readonly FilterPrimitive[];

interface FilterOption {
  keywords?: readonly string[];
  label: string;
  value: string;
}

type FilterOptionsLoader = (query: string) => Promise<readonly FilterOption[]>;

interface FilterDefinition<
  Item,
  Property extends string = string,
  Icon = unknown,
> {
  accessor: (item: Item) => FilterAccessorValue;
  emptyMessage?: string;
  icon: Icon;
  keywords?: readonly string[];
  label: string;
  loadOptions?: FilterOptionsLoader;
  operators?: readonly FilterOperator[];
  options?: readonly FilterOption[];
  property: Property;
  valueType: FilterValueType;
}

type FilterSchema<
  Item,
  Property extends string = string,
  Icon = unknown,
> = readonly FilterDefinition<Item, Property, Icon>[];

interface FilterCondition<Property extends string = string> {
  id: string;
  operator: FilterOperator;
  property: Property;
  type: "condition";
  values: readonly string[];
}

interface FilterGroup<Property extends string = string> {
  children: readonly FilterNode<Property>[];
  id: string;
  op: FilterGroupOperator;
  type: "group";
}

type FilterNode<Property extends string = string> =
  FilterCondition<Property> | FilterGroup<Property>;

function createEmptyFilterGroup<Property extends string>(
  id = "root",
): FilterGroup<Property> {
  return { children: [], id, op: "and", type: "group" };
}

export { createEmptyFilterGroup };
export type {
  FilterAccessorValue,
  FilterCondition,
  FilterDefinition,
  FilterGroup,
  FilterGroupOperator,
  FilterNode,
  FilterOperator,
  FilterOption,
  FilterOptionsLoader,
  FilterPrimitive,
  FilterSchema,
  FilterValueType,
};
