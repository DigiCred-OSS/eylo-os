import {
  CalendarDays,
  CircleDot,
  Clock3,
  MessageSquareText,
  Radio,
  Type,
} from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import { formatConversationEnum } from "@/features/conversations/conversation-formatters";
import {
  CONVERSATION_CHANNELS,
  CONVERSATION_STATUSES,
  type ConversationFilterProperty,
  type ConversationListItem,
  type ConversationSortField,
} from "@/features/conversations/conversations.types";

const CONVERSATION_FILTER_SCHEMA = [
  {
    accessor: (item: ConversationListItem) => item.conversation.status,
    icon: CircleDot,
    keywords: ["lifecycle", "state"],
    label: "Status",
    operators: ["is"],
    options: CONVERSATION_STATUSES.map((status) => ({
      keywords: [status.toLocaleLowerCase()],
      label: formatConversationEnum(status),
      value: status,
    })),
    property: "status",
    valueType: "multi-select",
  },
  {
    accessor: (item: ConversationListItem) => item.conversation.channel,
    icon: Radio,
    keywords: ["medium", "source", "voice", "text"],
    label: "Channel",
    operators: ["is"],
    options: CONVERSATION_CHANNELS.map((channel) => ({
      keywords: [channel.toLocaleLowerCase()],
      label: formatConversationEnum(channel),
      value: channel,
    })),
    property: "channel",
    valueType: "multi-select",
  },
] as const satisfies FilterUiSchema<
  ConversationListItem,
  ConversationFilterProperty
>;

const CONVERSATION_SORT_OPTIONS = [
  { icon: Clock3, label: "Updated", value: "updated_at" },
  { icon: CalendarDays, label: "Started", value: "created_at" },
  { icon: MessageSquareText, label: "Ended", value: "ended_at" },
  { icon: Type, label: "Title", value: "title" },
] as const satisfies readonly SortOption<ConversationSortField>[];

export { CONVERSATION_FILTER_SCHEMA, CONVERSATION_SORT_OPTIONS };
