import {
  BadgeCheck,
  CalendarClock,
  CircleDot,
  Power,
  Server,
  ShieldCheck,
  Type,
} from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import type {
  ProviderCapabilityDefinition,
  ProviderConfigRecord,
  ProviderFilterProperty,
  ProviderSortField,
} from "@/features/providers/providers.types";

const PROVIDER_SORT_OPTIONS = [
  { icon: Type, label: "Name", value: "name" },
  { icon: Server, label: "Provider", value: "provider" },
  { icon: CircleDot, label: "Ready", value: "ready" },
  { icon: CalendarClock, label: "Verified date", value: "verified_at" },
] as const satisfies readonly SortOption<ProviderSortField>[];

function createProviderFilterSchema(
  definition: ProviderCapabilityDefinition,
): FilterUiSchema<ProviderConfigRecord, ProviderFilterProperty> {
  return [
    {
      accessor: (config) => config.provider,
      icon: Server,
      keywords: ["vendor", "socket"],
      label: "Provider",
      operators: ["is"],
      options: definition.providers.map((provider) => ({
        keywords: [provider.id],
        label: provider.label,
        value: provider.id,
      })),
      property: "provider",
      valueType: "multi-select",
    },
    booleanFilter("ready", "Ready", CircleDot),
    booleanFilter("verified", "Verified", ShieldCheck),
    booleanFilter("enabled", "Enabled", Power),
  ];
}

function booleanFilter(
  property: Exclude<ProviderFilterProperty, "provider">,
  label: string,
  icon: typeof BadgeCheck,
) {
  return {
    accessor: (config: ProviderConfigRecord) => config[property],
    icon,
    label,
    operators: ["is"] as const,
    options: [
      { label: "Yes", value: "true" },
      { label: "No", value: "false" },
    ],
    property,
    valueType: "single-select" as const,
  };
}

export { createProviderFilterSchema, PROVIDER_SORT_OPTIONS };
