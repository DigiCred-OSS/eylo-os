import {
  BookOpenText,
  CalendarClock,
  Database,
  Globe2,
  PencilLine,
  SearchCheck,
  Type,
} from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import type {
  Knowledgebase,
  KnowledgeFilterProperty,
  KnowledgeSortField,
} from "@/features/knowledge/knowledge.types";

const KNOWLEDGE_SORT_OPTIONS = [
  { icon: Type, label: "Name", value: "name" },
  { icon: Database, label: "Search method", value: "vendor" },
  { icon: Globe2, label: "Scope", value: "scope" },
  { icon: CalendarClock, label: "Updated date", value: "updated_at" },
] as const satisfies readonly SortOption<KnowledgeSortField>[];

const KNOWLEDGE_FILTER_SCHEMA: FilterUiSchema<
  Knowledgebase,
  KnowledgeFilterProperty
> = [
  {
    accessor: (knowledgebase) => knowledgebase.vendor,
    icon: SearchCheck,
    keywords: ["retrieval", "semantic", "keyword"],
    label: "Search method",
    operators: ["is"],
    options: [
      {
        keywords: ["keyword", "lexical", "fts"],
        label: "Postgres full-text",
        value: "postgres_fts",
      },
      {
        keywords: ["semantic", "embedding", "vector"],
        label: "pgvector",
        value: "pgvector",
      },
    ],
    property: "vendor",
    valueType: "multi-select",
  },
  {
    accessor: (knowledgebase) => knowledgebase.scope,
    icon: BookOpenText,
    label: "Scope",
    operators: ["is"],
    options: [
      { label: "Organization", value: "organization" },
      { label: "Agent", value: "agent" },
      { label: "Conversation", value: "conversation" },
    ],
    property: "scope",
    valueType: "multi-select",
  },
  {
    accessor: (knowledgebase) => knowledgebase.writable,
    icon: PencilLine,
    label: "Accepts writes",
    operators: ["is"],
    options: [
      { label: "Yes", value: "true" },
      { label: "No", value: "false" },
    ],
    property: "writable",
    valueType: "single-select",
  },
];

export { KNOWLEDGE_FILTER_SCHEMA, KNOWLEDGE_SORT_OPTIONS };
