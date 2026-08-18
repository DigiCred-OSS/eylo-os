import { useState } from "react";
import { ArrowLeft, Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Input } from "@/components/ui/input";
import type { FilterUiDefinition } from "@/components/filters/filter-ui-types";
import { useFilterOptions } from "@/components/filters/use-filter-options";
import { cn } from "@/lib/utils";

interface FilterValuePickerProps<Item, Property extends string> {
  definition: FilterUiDefinition<Item, Property>;
  onBack?: () => void;
  onChange: (values: readonly string[]) => void;
  onDone?: () => void;
  selectedValues: readonly string[];
}

function FilterValuePicker<Item, Property extends string>({
  definition,
  onBack,
  onChange,
  onDone,
  selectedValues,
}: FilterValuePickerProps<Item, Property>) {
  const [query, setQuery] = useState("");
  const { error, isLoading, options } = useFilterOptions(definition, query);

  if (definition.valueType === "date") {
    return (
      <DateValuePicker
        definition={definition}
        onBack={onBack}
        onChange={onChange}
        onDone={onDone}
        selectedValues={selectedValues}
      />
    );
  }

  const allowsMultipleValues = definition.valueType !== "single-select";
  const emptyMessage = isLoading
    ? "Loading values…"
    : (error ?? definition.emptyMessage ?? "No values found.");

  return (
    <div>
      <PickerBackButton label={definition.label} onBack={onBack} />
      <Command>
        <CommandInput
          aria-label={`Search ${definition.label} values`}
          placeholder={`Search ${definition.label.toLocaleLowerCase()}…`}
          value={query}
          onValueChange={setQuery}
        />
        <CommandList aria-multiselectable={allowsMultipleValues || undefined}>
          <CommandEmpty>{emptyMessage}</CommandEmpty>
          <CommandGroup heading={definition.label}>
            {options.map((option) => {
              const selected = selectedValues.includes(option.value);
              return (
                <CommandItem
                  aria-checked={allowsMultipleValues ? selected : undefined}
                  key={option.value}
                  keywords={option.keywords ? [...option.keywords] : undefined}
                  value={`${definition.label} ${option.label}`}
                  onSelect={() => {
                    if (!allowsMultipleValues) {
                      onChange([option.value]);
                      onDone?.();
                      return;
                    }
                    onChange(
                      selected
                        ? selectedValues.filter(
                            (value) => value !== option.value,
                          )
                        : [...selectedValues, option.value],
                    );
                  }}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "flex size-4 shrink-0 items-center justify-center rounded-[4px] border",
                      selected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-input text-transparent",
                    )}
                  >
                    <Check className="size-3.5" />
                  </span>
                  <span className="truncate">{option.label}</span>
                </CommandItem>
              );
            })}
          </CommandGroup>
        </CommandList>
      </Command>
      {allowsMultipleValues && onDone !== undefined ? (
        <div className="flex justify-end border-t p-2">
          <Button size="sm" variant="outline" onClick={onDone}>
            Done
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function DateValuePicker<Item, Property extends string>({
  definition,
  onBack,
  onChange,
  onDone,
  selectedValues,
}: FilterValuePickerProps<Item, Property>) {
  return (
    <div>
      <PickerBackButton label={definition.label} onBack={onBack} />
      <div className="space-y-2 p-3">
        <label
          className="text-sm font-medium"
          htmlFor={`filter-${definition.property}`}
        >
          {definition.label}
        </label>
        <Input
          id={`filter-${definition.property}`}
          type="date"
          value={selectedValues[0] ?? ""}
          onChange={(event) =>
            onChange(event.target.value === "" ? [] : [event.target.value])
          }
        />
        {onDone !== undefined ? (
          <Button
            className="w-full"
            disabled={selectedValues.length === 0}
            size="sm"
            onClick={onDone}
          >
            Apply date
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function PickerBackButton({
  label,
  onBack,
}: {
  label: string;
  onBack?: () => void;
}) {
  return onBack === undefined ? null : (
    <div className="border-b p-1">
      <Button
        className="w-full justify-start"
        size="sm"
        variant="ghost"
        onClick={onBack}
      >
        <ArrowLeft aria-hidden="true" />
        {label}
      </Button>
    </div>
  );
}

export { FilterValuePicker };
