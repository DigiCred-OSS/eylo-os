import { CalendarClock, Database, ListOrdered, Radio } from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import { voiceRuntimeMode } from "@/features/voice/voice.query";
import type {
  VoiceConfigRecord,
  VoiceFilterProperty,
  VoiceSortField,
} from "@/features/voice/voice.types";

const VOICE_SORT_OPTIONS = [
  { icon: Database, label: "Name", value: "name" },
  { icon: ListOrdered, label: "Revision", value: "revision" },
  { icon: CalendarClock, label: "Updated date", value: "updated_at" },
] as const satisfies readonly SortOption<VoiceSortField>[];

const VOICE_FILTER_SCHEMA: FilterUiSchema<
  VoiceConfigRecord,
  VoiceFilterProperty
> = [
  {
    accessor: voiceRuntimeMode,
    icon: Radio,
    keywords: ["speech", "stt", "tts", "live"],
    label: "Runtime",
    operators: ["is"],
    options: [
      { label: "Decomposed", value: "decomposed" },
      { label: "Realtime", value: "realtime" },
    ],
    property: "runtime",
    valueType: "multi-select",
  },
  {
    accessor: (voiceConfig) =>
      voiceConfig.config.artifacts?.audio_storage_enabled ?? false,
    icon: Database,
    label: "Stores recordings",
    operators: ["is"],
    options: [
      { label: "Yes", value: "true" },
      { label: "No", value: "false" },
    ],
    property: "audio_storage",
    valueType: "single-select",
  },
];

export { VOICE_FILTER_SCHEMA, VOICE_SORT_OPTIONS };
