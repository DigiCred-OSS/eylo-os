import { useState } from "react";
import { Check, X } from "lucide-react";

import { FilterValuePicker } from "@/components/filters/FilterValuePicker";
import type { FilterUiDefinition } from "@/components/filters/filter-ui-types";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  getFilterOperatorLabel,
  getFilterOperators,
  normalizeFilterOperator,
  type FilterCondition,
  type FilterOperator,
} from "@/lib/filters";

interface FilterPillProps<Item, Property extends string> {
  condition: FilterCondition<Property>;
  definition: FilterUiDefinition<Item, Property>;
  onChange: (condition: FilterCondition<Property>) => void;
  onRemove: () => void;
}

function FilterPill<Item, Property extends string>({
  condition,
  definition,
  onChange,
  onRemove,
}: FilterPillProps<Item, Property>) {
  const [operatorOpen, setOperatorOpen] = useState(false);
  const [valueOpen, setValueOpen] = useState(false);
  const Icon = definition.icon;
  const operators = getFilterOperators(definition, condition.values.length);

  function changeOperator(operator: FilterOperator): void {
    onChange({ ...condition, operator });
    setOperatorOpen(false);
  }

  function changeValues(values: readonly string[]): void {
    onChange({
      ...condition,
      operator: normalizeFilterOperator(
        condition.operator,
        definition.valueType,
        values.length,
      ),
      values,
    });
  }

  return (
    <div className="inline-flex h-8 max-w-full items-stretch overflow-hidden rounded-md border bg-background text-xs">
      <span className="inline-flex shrink-0 items-center gap-1.5 border-r px-2 font-medium">
        <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
        {definition.label}
      </span>

      <Popover open={operatorOpen} onOpenChange={setOperatorOpen}>
        <PopoverTrigger
          render={
            <button
              aria-label={`Change ${definition.label} filter operator`}
              className="shrink-0 border-r px-2 text-muted-foreground outline-none hover:bg-muted focus-visible:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50"
              type="button"
            />
          }
        >
          {getFilterOperatorLabel(condition.operator, condition.values.length)}
        </PopoverTrigger>
        <PopoverContent align="start" className="w-48 gap-0 p-0">
          <Command>
            <CommandList>
              <CommandGroup heading="Operator">
                {operators.map((operator) => (
                  <CommandItem
                    key={operator}
                    value={getFilterOperatorLabel(
                      operator,
                      condition.values.length,
                    )}
                    onSelect={() => changeOperator(operator)}
                  >
                    <Check
                      className={
                        condition.operator === operator
                          ? "opacity-100"
                          : "opacity-0"
                      }
                      aria-hidden="true"
                    />
                    {getFilterOperatorLabel(operator, condition.values.length)}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      <Popover open={valueOpen} onOpenChange={setValueOpen}>
        <PopoverTrigger
          render={
            <button
              aria-label={`Edit ${definition.label} filter values`}
              className="min-w-0 max-w-56 truncate px-2 font-medium outline-none hover:bg-muted focus-visible:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50"
              type="button"
            />
          }
        >
          {getFilterValueLabel(definition, condition.values)}
        </PopoverTrigger>
        <PopoverContent align="start" className="w-72 gap-0 p-0">
          <FilterValuePicker
            definition={definition}
            selectedValues={condition.values}
            onChange={changeValues}
            onDone={() => setValueOpen(false)}
          />
        </PopoverContent>
      </Popover>

      <button
        aria-label={`Remove ${definition.label} filter`}
        className="inline-flex w-8 shrink-0 items-center justify-center border-l text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50"
        type="button"
        onClick={onRemove}
      >
        <X className="size-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

function getFilterValueLabel<Item, Property extends string>(
  definition: FilterUiDefinition<Item, Property>,
  values: readonly string[],
): string {
  const labels = values.map(
    (value) =>
      definition.options?.find((option) => option.value === value)?.label ??
      value,
  );
  if (labels.length === 0) {
    return "Choose value";
  }
  if (labels.length <= 2) {
    return labels.join(", ");
  }
  return `${labels.slice(0, 2).join(", ")} +${labels.length - 2}`;
}

export { FilterPill };
