import { useState } from "react";
import { Check, ListFilter, SlidersHorizontal } from "lucide-react";

import { FilterPill } from "@/components/filters/FilterPill";
import { FilterValuePicker } from "@/components/filters/FilterValuePicker";
import type {
  FilterUiDefinition,
  FilterUiSchema,
} from "@/components/filters/filter-ui-types";
import { useFilterOptions } from "@/components/filters/use-filter-options";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  appendFilterNode,
  getDefaultFilterOperator,
  normalizeFilterOperator,
  removeFilterNode,
  replaceFilterNode,
  type FilterCondition,
  type FilterGroup,
  type FilterOption,
} from "@/lib/filters";

interface FilterProps<Item, Property extends string> {
  filterTree: FilterGroup<Property>;
  listLabel: string;
  onAdvancedOpen?: () => void;
  onChange: (filterTree: FilterGroup<Property>) => void;
  schema: FilterUiSchema<Item, Property>;
}

function FilterControl<Item, Property extends string>({
  filterTree,
  listLabel,
  onAdvancedOpen,
  onChange,
  schema,
}: FilterProps<Item, Property>) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [draftCondition, setDraftCondition] =
    useState<FilterCondition<Property> | null>(null);
  const directConditions = filterTree.children.filter(
    (node): node is FilterCondition<Property> =>
      node.type === "condition" && node.values.length > 0,
  );
  const activeProperties = new Set(
    directConditions.map((condition) => condition.property),
  );
  const availableDefinitions = schema.filter(
    (definition) => !activeProperties.has(definition.property),
  );
  const selectedDefinition =
    draftCondition === null
      ? undefined
      : schema.find(
          (definition) => definition.property === draftCondition.property,
        );

  function closeMenu(): void {
    setOpen(false);
    setQuery("");
    setDraftCondition(null);
  }

  function startFilter(definition: FilterUiDefinition<Item, Property>): void {
    setDraftCondition({
      id: createFilterId(definition.property),
      operator: getDefaultFilterOperator(definition.valueType),
      property: definition.property,
      type: "condition",
      values: [],
    });
    setQuery("");
  }

  function updateDraft(values: readonly string[]): void {
    if (draftCondition === null || selectedDefinition === undefined) {
      return;
    }
    const nextCondition = {
      ...draftCondition,
      operator: normalizeFilterOperator(
        draftCondition.operator,
        selectedDefinition.valueType,
        values.length,
      ),
      values,
    };
    setDraftCondition(nextCondition);
    onChange(upsertDirectCondition(filterTree, nextCondition));
  }

  function addQuickValue(
    definition: FilterUiDefinition<Item, Property>,
    option: FilterOption,
  ): void {
    const condition: FilterCondition<Property> = {
      id: createFilterId(definition.property),
      operator: getDefaultFilterOperator(definition.valueType),
      property: definition.property,
      type: "condition",
      values: [option.value],
    };
    onChange(appendFilterNode(filterTree, filterTree.id, condition));
    closeMenu();
  }

  return (
    <Popover
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) {
          setQuery("");
          setDraftCondition(null);
        }
      }}
    >
      <PopoverTrigger
        render={
          <Button
            aria-label={`Add ${listLabel} filter`}
            size="sm"
            variant="outline"
          />
        }
      >
        <ListFilter aria-hidden="true" />
        <span className="hidden sm:inline">Filter</span>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 gap-0 p-0">
        {draftCondition !== null && selectedDefinition !== undefined ? (
          <FilterValuePicker
            definition={selectedDefinition}
            selectedValues={draftCondition.values}
            onBack={() => setDraftCondition(null)}
            onChange={updateDraft}
            onDone={closeMenu}
          />
        ) : (
          <Command>
            <CommandInput
              aria-label="Search filter properties and values"
              placeholder="Filter by…"
              value={query}
              onValueChange={setQuery}
            />
            <CommandList>
              <CommandEmpty>No filters found.</CommandEmpty>
              <CommandGroup heading="Filters">
                {availableDefinitions.map((definition) => {
                  const Icon = definition.icon;
                  const optionKeywords = definition.options?.flatMap(
                    (option) => [option.label, ...(option.keywords ?? [])],
                  );
                  return (
                    <CommandItem
                      key={definition.property}
                      keywords={[
                        ...(definition.keywords ?? []),
                        ...(optionKeywords ?? []),
                      ]}
                      value={definition.label}
                      onSelect={() => startFilter(definition)}
                    >
                      <Icon
                        className="text-muted-foreground"
                        aria-hidden="true"
                      />
                      {definition.label}
                    </CommandItem>
                  );
                })}
              </CommandGroup>

              {query.trim() !== "" ? (
                <CommandGroup heading="Values">
                  {availableDefinitions.map((definition) => (
                    <QuickFilterValues
                      definition={definition}
                      key={definition.property}
                      query={query}
                      onSelect={(option) => addQuickValue(definition, option)}
                    />
                  ))}
                </CommandGroup>
              ) : null}

              {onAdvancedOpen !== undefined ? (
                <CommandGroup heading="Advanced">
                  <CommandItem
                    value="Advanced filter AND OR groups"
                    onSelect={() => {
                      closeMenu();
                      onAdvancedOpen();
                    }}
                  >
                    <SlidersHorizontal
                      className="text-muted-foreground"
                      aria-hidden="true"
                    />
                    Advanced filter
                  </CommandItem>
                </CommandGroup>
              ) : null}
            </CommandList>
          </Command>
        )}
      </PopoverContent>
    </Popover>
  );
}

function AppliedFilterBar<Item, Property extends string>({
  filterTree,
  listLabel,
  onAdvancedOpen,
  onChange,
  schema,
}: FilterProps<Item, Property>) {
  const directConditions = filterTree.children.filter(
    (node): node is FilterCondition<Property> =>
      node.type === "condition" && node.values.length > 0,
  );
  const advancedConditionCount = countNestedConditions(filterTree);
  const conditionCount = directConditions.length + advancedConditionCount;

  if (conditionCount === 0) {
    return null;
  }

  return (
    <div
      aria-label={`Applied ${listLabel} filters`}
      className="flex min-w-0 flex-wrap items-center gap-1.5"
    >
      {directConditions.map((condition) => {
        const definition = schema.find(
          (candidate) => candidate.property === condition.property,
        );
        return definition === undefined ? null : (
          <FilterPill
            condition={condition}
            definition={definition}
            key={condition.id}
            onChange={(nextCondition) =>
              onChange(
                nextCondition.values.length === 0
                  ? removeFilterNode(filterTree, nextCondition.id)
                  : replaceFilterNode(filterTree, nextCondition),
              )
            }
            onRemove={() =>
              onChange(removeFilterNode(filterTree, condition.id))
            }
          />
        );
      })}

      {advancedConditionCount > 0 && onAdvancedOpen !== undefined ? (
        <Button size="sm" variant="outline" onClick={onAdvancedOpen}>
          <SlidersHorizontal aria-hidden="true" />
          Advanced · {advancedConditionCount}
        </Button>
      ) : null}

      {conditionCount > 1 ? (
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onChange({ ...filterTree, children: [] })}
        >
          Clear all
        </Button>
      ) : null}
    </div>
  );
}

function QuickFilterValues<Item, Property extends string>({
  definition,
  onSelect,
  query,
}: {
  definition: FilterUiDefinition<Item, Property>;
  onSelect: (option: FilterOption) => void;
  query: string;
}) {
  const { options } = useFilterOptions(definition, query, query.trim() !== "");
  const Icon = definition.icon;
  return options.map((option) => (
    <CommandItem
      key={`${definition.property}-${option.value}`}
      keywords={option.keywords ? [...option.keywords] : undefined}
      value={`${definition.label} ${option.label}`}
      onSelect={() => onSelect(option)}
    >
      <Icon className="text-muted-foreground" aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate">{option.label}</span>
      <span className="text-xs text-muted-foreground">{definition.label}</span>
      <Check className="opacity-0" aria-hidden="true" />
    </CommandItem>
  ));
}

function upsertDirectCondition<Property extends string>(
  root: FilterGroup<Property>,
  condition: FilterCondition<Property>,
): FilterGroup<Property> {
  const exists = root.children.some((child) => child.id === condition.id);
  if (condition.values.length === 0) {
    return exists ? removeFilterNode(root, condition.id) : root;
  }
  return exists
    ? replaceFilterNode(root, condition)
    : appendFilterNode(root, root.id, condition);
}

function countNestedConditions<Property extends string>(
  root: FilterGroup<Property>,
): number {
  return root.children.reduce((count, child) => {
    if (child.type === "condition") {
      return count;
    }
    return count + countAllConditions(child);
  }, 0);
}

function countAllConditions<Property extends string>(
  group: FilterGroup<Property>,
): number {
  return group.children.reduce(
    (count, child) =>
      count + (child.type === "condition" ? 1 : countAllConditions(child)),
    0,
  );
}

function createFilterId(property: string): string {
  return `${property}-${globalThis.crypto.randomUUID()}`;
}

export { AppliedFilterBar, FilterControl };
