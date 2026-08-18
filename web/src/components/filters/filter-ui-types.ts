import type { LucideIcon } from "lucide-react";

import type { FilterDefinition, FilterSchema } from "@/lib/filters";

type FilterUiDefinition<Item, Property extends string> = FilterDefinition<
  Item,
  Property,
  LucideIcon
>;

type FilterUiSchema<Item, Property extends string> = FilterSchema<
  Item,
  Property,
  LucideIcon
>;

export type { FilterUiDefinition, FilterUiSchema };
