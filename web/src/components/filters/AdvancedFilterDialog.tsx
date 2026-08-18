import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";

import { FilterPill } from "@/components/filters/FilterPill";
import type { FilterUiSchema } from "@/components/filters/filter-ui-types";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  appendFilterNode,
  getDefaultFilterOperator,
  pruneFilterTree,
  removeFilterNode,
  replaceFilterNode,
  type FilterCondition,
  type FilterGroup,
  type FilterGroupOperator,
} from "@/lib/filters";
import { cn } from "@/lib/utils";

interface AdvancedFilterDialogProps<Item, Property extends string> {
  filterTree: FilterGroup<Property>;
  listLabel: string;
  onApply: (filterTree: FilterGroup<Property>) => void;
  onChange: (filterTree: FilterGroup<Property>) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  schema: FilterUiSchema<Item, Property>;
}

function AdvancedFilterDialog<Item, Property extends string>({
  filterTree,
  listLabel,
  onApply,
  onChange,
  onOpenChange,
  open,
  schema,
}: AdvancedFilterDialogProps<Item, Property>) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-hidden sm:max-w-2xl">
        <DialogHeader className="pr-8">
          <DialogTitle>Advanced {listLabel} filters</DialogTitle>
          <DialogDescription>
            Group conditions and choose whether all or any must match.
          </DialogDescription>
        </DialogHeader>

        <div className="overflow-y-auto pr-1">
          <FilterGroupEditor
            filterGroup={filterTree}
            schema={schema}
            onChange={onChange}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              onApply(pruneFilterTree(filterTree));
              onOpenChange(false);
            }}
          >
            Apply filters
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FilterGroupEditor<Item, Property extends string>({
  filterGroup,
  isNested = false,
  onChange,
  onRemove,
  schema,
}: {
  filterGroup: FilterGroup<Property>;
  isNested?: boolean;
  onChange: (filterGroup: FilterGroup<Property>) => void;
  onRemove?: () => void;
  schema: FilterUiSchema<Item, Property>;
}) {
  return (
    <section
      aria-label={isNested ? "Nested filter group" : "Main filter group"}
      className={cn("space-y-3 rounded-md border p-3", isNested && "ml-4")}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <GroupLogicControl
          value={filterGroup.op}
          onChange={(op) => onChange({ ...filterGroup, op })}
        />
        {onRemove !== undefined ? (
          <Button
            aria-label="Remove filter group"
            size="icon-xs"
            variant="ghost"
            onClick={onRemove}
          >
            <Trash2 aria-hidden="true" />
          </Button>
        ) : null}
      </div>

      <div className="space-y-2">
        {filterGroup.children.length === 0 ? (
          <p className="py-3 text-center text-sm text-muted-foreground">
            Add a condition or nested group.
          </p>
        ) : null}
        {filterGroup.children.map((child) => {
          if (child.type === "group") {
            return (
              <FilterGroupEditor
                filterGroup={child}
                isNested
                key={child.id}
                schema={schema}
                onChange={(nextGroup) =>
                  onChange(replaceFilterNode(filterGroup, nextGroup))
                }
                onRemove={() =>
                  onChange(removeFilterNode(filterGroup, child.id))
                }
              />
            );
          }

          const definition = schema.find(
            (candidate) => candidate.property === child.property,
          );
          if (definition === undefined) {
            return (
              <div
                className="flex items-center justify-between gap-2 rounded-md border px-3 py-2"
                key={child.id}
                role="alert"
              >
                <span className="text-sm text-muted-foreground">
                  This filter property is no longer available.
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    onChange(removeFilterNode(filterGroup, child.id))
                  }
                >
                  Remove
                </Button>
              </div>
            );
          }

          return (
            <FilterPill
              condition={child}
              definition={definition}
              key={child.id}
              onChange={(condition) =>
                onChange(replaceFilterNode(filterGroup, condition))
              }
              onRemove={() => onChange(removeFilterNode(filterGroup, child.id))}
            />
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <AddConditionButton
          schema={schema}
          onAdd={(condition) =>
            onChange(appendFilterNode(filterGroup, filterGroup.id, condition))
          }
        />
        <Button
          size="sm"
          variant="ghost"
          onClick={() =>
            onChange(
              appendFilterNode(filterGroup, filterGroup.id, {
                children: [],
                id: createFilterId("group"),
                op: "and",
                type: "group",
              }),
            )
          }
        >
          <Plus aria-hidden="true" />
          Add group
        </Button>
      </div>
    </section>
  );
}

function GroupLogicControl({
  onChange,
  value,
}: {
  onChange: (value: FilterGroupOperator) => void;
  value: FilterGroupOperator;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-medium text-muted-foreground">Match</span>
      <div className="inline-flex rounded-md border p-0.5">
        {(["and", "or"] as const).map((operator) => (
          <Button
            aria-pressed={value === operator}
            key={operator}
            size="xs"
            variant={value === operator ? "secondary" : "ghost"}
            onClick={() => onChange(operator)}
          >
            {operator.toUpperCase()}
          </Button>
        ))}
      </div>
    </div>
  );
}

function AddConditionButton<Item, Property extends string>({
  onAdd,
  schema,
}: {
  onAdd: (condition: FilterCondition<Property>) => void;
  schema: FilterUiSchema<Item, Property>;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button size="sm" variant="outline" />}>
        <Plus aria-hidden="true" />
        Add condition
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 gap-0 p-0">
        <Command>
          <CommandInput
            aria-label="Search filter properties"
            placeholder="Choose property…"
          />
          <CommandList>
            <CommandEmpty>No properties found.</CommandEmpty>
            <CommandGroup heading="Properties">
              {schema.map((definition) => {
                const Icon = definition.icon;
                return (
                  <CommandItem
                    key={definition.property}
                    value={definition.label}
                    onSelect={() => {
                      onAdd({
                        id: createFilterId(definition.property),
                        operator: getDefaultFilterOperator(
                          definition.valueType,
                        ),
                        property: definition.property,
                        type: "condition",
                        values: [],
                      });
                      setOpen(false);
                    }}
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
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

function createFilterId(prefix: string): string {
  return `${prefix}-${globalThis.crypto.randomUUID()}`;
}

export { AdvancedFilterDialog };
