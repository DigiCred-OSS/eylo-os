import {
  Check,
  ChevronsUpDown,
  Eye,
  EyeOff,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { useMemo, useState, type ChangeEvent } from "react";
import { Link } from "react-router";

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
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type {
  ProviderConfigRecord,
  ProviderFieldDefinition,
  ProviderFieldValue,
} from "@/features/providers/providers.types";
import { cn } from "@/lib/utils";

const UNSET_VALUE = "__eylo_unset__";

interface ProviderFieldControlProps {
  configureReferencePath?: string;
  error?: string;
  existingSecret: boolean;
  field: ProviderFieldDefinition;
  idPrefix: string;
  onChange: (value: ProviderFieldValue | string | null | undefined) => void;
  referenceOptions: readonly ProviderConfigRecord[];
  required: boolean;
  value: ProviderFieldValue | string | null | undefined;
}

function ProviderFieldControl({
  configureReferencePath,
  error,
  existingSecret,
  field,
  idPrefix,
  onChange,
  referenceOptions,
  required,
  value,
}: ProviderFieldControlProps) {
  const id = `${idPrefix}-${field.key}`;
  const descriptionId = `${id}-description`;
  const errorId = `${id}-error`;
  const describedBy = [
    field.description ? descriptionId : null,
    error ? errorId : null,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>
        {field.label}
        {required ? (
          <span className="ml-1 text-destructive" aria-label="required">
            *
          </span>
        ) : null}
      </Label>
      {field.secret ? (
        <SecretControl
          describedBy={describedBy}
          existingSecret={existingSecret}
          field={field}
          id={id}
          invalid={error !== undefined}
          value={value}
          onChange={onChange}
        />
      ) : field.kind === "select" ? (
        <SelectControl
          describedBy={describedBy}
          field={field}
          id={id}
          invalid={error !== undefined}
          value={value}
          onChange={onChange}
        />
      ) : field.kind === "boolean" ? (
        <BooleanControl
          describedBy={describedBy}
          id={id}
          invalid={error !== undefined}
          value={value}
          onChange={onChange}
        />
      ) : field.kind === "string_list" ? (
        <Textarea
          id={id}
          aria-describedby={describedBy || undefined}
          aria-invalid={error !== undefined}
          rows={4}
          placeholder="One value per line"
          value={Array.isArray(value) ? value.join("\n") : ""}
          onChange={(event) =>
            onChange(
              event.target.value === ""
                ? []
                : event.target.value.split("\n").map((item) => item.trim()),
            )
          }
        />
      ) : field.kind === "provider_config" ? (
        <ReferenceControl
          configureReferencePath={configureReferencePath}
          describedBy={describedBy}
          field={field}
          id={id}
          invalid={error !== undefined}
          options={referenceOptions}
          value={value}
          onChange={onChange}
        />
      ) : (
        <Input
          id={id}
          aria-describedby={describedBy || undefined}
          aria-invalid={error !== undefined}
          max={field.maximum ?? undefined}
          min={field.minimum ?? undefined}
          step={
            field.kind === "integer"
              ? 1
              : field.kind === "number"
                ? "any"
                : undefined
          }
          type={
            field.kind === "integer" || field.kind === "number"
              ? "number"
              : "text"
          }
          value={toInputValue(value)}
          onChange={(event) =>
            onChange(
              field.kind === "integer" || field.kind === "number"
                ? parseNumber(event.target.value)
                : event.target.value,
            )
          }
        />
      )}

      {field.description ? (
        <p
          id={descriptionId}
          className="text-xs leading-5 text-muted-foreground"
        >
          {field.description}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function SecretControl({
  describedBy,
  existingSecret,
  field,
  id,
  invalid,
  onChange,
  value,
}: {
  describedBy: string;
  existingSecret: boolean;
  field: ProviderFieldDefinition;
  id: string;
  invalid: boolean;
  onChange: ProviderFieldControlProps["onChange"];
  value: ProviderFieldControlProps["value"];
}) {
  const [revealed, setRevealed] = useState(false);
  const isRemoved = value === null;
  const textValue = typeof value === "string" ? value : "";
  const inputProps = {
    "aria-describedby": describedBy || undefined,
    "aria-invalid": invalid,
    autoComplete: "new-password",
    id,
    placeholder: existingSecret
      ? "Stored — leave blank to keep"
      : "Enter credential",
    value: textValue,
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onChange(event.target.value),
  };

  if (isRemoved) {
    return (
      <div className="flex items-center justify-between gap-3 border border-warning/40 bg-warning/10 p-3">
        <p className="text-sm">Stored credential will be removed on save.</p>
        <Button
          size="sm"
          type="button"
          variant="outline"
          onClick={() => onChange(undefined)}
        >
          <RotateCcw aria-hidden="true" />
          Undo
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        {field.multiline ? (
          <Textarea
            {...inputProps}
            className={revealed ? undefined : "[-webkit-text-security:disc]"}
            rows={5}
            spellCheck={false}
          />
        ) : (
          <Input
            {...inputProps}
            type={revealed ? "text" : "password"}
            spellCheck={false}
          />
        )}
        <Button
          className="shrink-0"
          type="button"
          variant="outline"
          size="icon"
          aria-label={revealed ? `Hide ${field.label}` : `Show ${field.label}`}
          title={revealed ? "Hide credential" : "Show credential"}
          onClick={() => setRevealed((current) => !current)}
        >
          {revealed ? (
            <EyeOff aria-hidden="true" />
          ) : (
            <Eye aria-hidden="true" />
          )}
        </Button>
      </div>
      {existingSecret ? (
        <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
          <span>A credential is stored. New input replaces it.</span>
          <Button
            className="h-auto px-1 py-0 text-destructive"
            type="button"
            variant="ghost"
            onClick={() => onChange(null)}
          >
            <Trash2 aria-hidden="true" />
            Remove
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function SelectControl({
  describedBy,
  field,
  id,
  invalid,
  onChange,
  value,
}: {
  describedBy: string;
  field: ProviderFieldDefinition;
  id: string;
  invalid: boolean;
  onChange: ProviderFieldControlProps["onChange"];
  value: ProviderFieldControlProps["value"];
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const selected =
    typeof value === "string" && value !== "" ? value : UNSET_VALUE;
  const currentOption = field.options.find(
    (option) => option.value === selected,
  );
  const options = useMemo(
    () =>
      selected !== UNSET_VALUE && currentOption === undefined
        ? [
            {
              label: `Current saved value · ${selected}`,
              value: selected,
            },
            ...field.options,
          ]
        : field.options,
    [currentOption, field.options, selected],
  );
  const customValue = query.trim();
  const normalizedCustomValue = customValue.toLocaleLowerCase();
  const catalogMatchesQuery = options.some(
    (option) =>
      option.value.toLocaleLowerCase().includes(normalizedCustomValue) ||
      option.label.toLocaleLowerCase().includes(normalizedCustomValue),
  );

  function choose(next: string | null): void {
    onChange(next);
    setOpen(false);
    setQuery("");
  }

  return (
    <Popover
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (!nextOpen) {
          setQuery("");
        }
      }}
    >
      <PopoverTrigger
        render={
          <Button
            id={id}
            className="w-full justify-between overflow-hidden font-normal"
            type="button"
            variant="outline"
            role="combobox"
            aria-describedby={describedBy || undefined}
            aria-expanded={open}
            aria-invalid={invalid}
            aria-label={`Choose ${field.label.toLocaleLowerCase()}`}
          />
        }
      >
        <span className="min-w-0 truncate text-left">
          {selected === UNSET_VALUE
            ? `Choose ${field.label.toLocaleLowerCase()}`
            : (currentOption?.label ?? selected)}
        </span>
        <ChevronsUpDown
          className="ml-2 size-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-(--anchor-width) min-w-72 max-w-[calc(100vw-2rem)] gap-0 p-0 sm:max-w-lg"
      >
        <Command>
          <CommandInput
            aria-label={`Search ${field.label}`}
            placeholder={`Search ${field.label.toLocaleLowerCase()}…`}
            value={query}
            onValueChange={setQuery}
          />
          <CommandList>
            <CommandEmpty>No matching options.</CommandEmpty>
            <CommandGroup heading={field.label}>
              <CommandItem value="Choose later" onSelect={() => choose(null)}>
                <Check
                  className={cn(
                    "text-muted-foreground",
                    selected === UNSET_VALUE ? "opacity-100" : "opacity-0",
                  )}
                  aria-hidden="true"
                />
                <span className="text-muted-foreground">Choose later</span>
              </CommandItem>
              {options.map((option) => (
                <CommandItem
                  key={option.value}
                  value={`${option.label} ${option.value}`}
                  onSelect={() => choose(option.value)}
                >
                  <Check
                    className={cn(
                      "text-muted-foreground",
                      selected === option.value ? "opacity-100" : "opacity-0",
                    )}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 break-words">{option.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
            {field.allow_custom &&
            customValue !== "" &&
            !catalogMatchesQuery ? (
              <CommandGroup heading="Custom value">
                <CommandItem
                  value={`Use custom value ${customValue}`}
                  onSelect={() => choose(customValue)}
                >
                  <Check className="opacity-0" aria-hidden="true" />
                  <span className="min-w-0 break-all">Use “{customValue}”</span>
                </CommandItem>
              </CommandGroup>
            ) : null}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

function BooleanControl({
  describedBy,
  id,
  invalid,
  onChange,
  value,
}: {
  describedBy: string;
  id: string;
  invalid: boolean;
  onChange: ProviderFieldControlProps["onChange"];
  value: ProviderFieldControlProps["value"];
}) {
  const selected = typeof value === "boolean" ? String(value) : UNSET_VALUE;
  return (
    <Select
      value={selected}
      onValueChange={(next) =>
        onChange(next === UNSET_VALUE ? null : next === "true")
      }
    >
      <SelectTrigger
        id={id}
        className="w-full"
        aria-describedby={describedBy || undefined}
        aria-invalid={invalid}
      >
        <SelectValue>
          {selected === UNSET_VALUE
            ? "Choose yes or no"
            : selected === "true"
              ? "Yes"
              : "No"}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={UNSET_VALUE}>Choose later</SelectItem>
        <SelectItem value="true">Yes</SelectItem>
        <SelectItem value="false">No</SelectItem>
      </SelectContent>
    </Select>
  );
}

function ReferenceControl({
  configureReferencePath,
  describedBy,
  field,
  id,
  invalid,
  onChange,
  options,
  value,
}: {
  configureReferencePath?: string;
  describedBy: string;
  field: ProviderFieldDefinition;
  id: string;
  invalid: boolean;
  onChange: ProviderFieldControlProps["onChange"];
  options: readonly ProviderConfigRecord[];
  value: ProviderFieldControlProps["value"];
}) {
  const selected =
    typeof value === "string" && value !== "" ? value : UNSET_VALUE;
  return (
    <div className="space-y-2">
      <Select
        value={selected}
        onValueChange={(next) => onChange(next === UNSET_VALUE ? null : next)}
      >
        <SelectTrigger
          id={id}
          className="w-full"
          aria-describedby={describedBy || undefined}
          aria-invalid={invalid}
        >
          <SelectValue>
            {selected === UNSET_VALUE
              ? `Choose ${field.label.toLocaleLowerCase()}`
              : (options.find((option) => option.id === selected)?.name ??
                selected)}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={UNSET_VALUE}>Choose later</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.name} · {option.provider}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {options.length === 0 && configureReferencePath !== undefined ? (
        <p className="text-xs text-muted-foreground">
          No ready configurations.{" "}
          <Link
            className="font-medium text-foreground underline underline-offset-4"
            to={configureReferencePath}
          >
            Configure {field.reference_capability}
          </Link>
        </p>
      ) : null}
    </div>
  );
}

function parseNumber(value: string): number | null {
  if (value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function toInputValue(
  value: ProviderFieldControlProps["value"],
): string | number {
  return typeof value === "string" || typeof value === "number" ? value : "";
}

export { ProviderFieldControl };
