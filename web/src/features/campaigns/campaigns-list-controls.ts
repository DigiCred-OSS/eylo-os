import {
  CalendarClock,
  CircleGauge,
  MessageCircleMore,
  Target,
  Type,
} from "lucide-react";

import type { FilterUiSchema, SortOption } from "@/components/filters";
import { formatCampaignEnum } from "@/features/campaigns/campaign-formatters";
import type {
  Campaign,
  CampaignFilterProperty,
  CampaignSortField,
} from "@/features/campaigns/campaigns.types";

const CAMPAIGN_STATUSES = [
  "draft",
  "scheduled",
  "running",
  "paused",
  "completed",
  "canceled",
] as const;
const CAMPAIGN_CHANNELS = ["voice", "email", "widget"] as const;

const CAMPAIGN_FILTER_SCHEMA: FilterUiSchema<Campaign, CampaignFilterProperty> =
  [
    {
      accessor: (campaign) => campaign.status,
      icon: CircleGauge,
      label: "Status",
      operators: ["is"],
      options: CAMPAIGN_STATUSES.map(option),
      property: "status",
      valueType: "multi-select",
    },
    {
      accessor: (campaign) => campaign.channel,
      icon: MessageCircleMore,
      label: "Channel",
      operators: ["is"],
      options: CAMPAIGN_CHANNELS.map(option),
      property: "channel",
      valueType: "multi-select",
    },
  ];

const CAMPAIGN_SORT_OPTIONS = [
  { icon: CalendarClock, label: "Updated date", value: "updated_at" },
  { icon: Type, label: "Name", value: "name" },
  { icon: CircleGauge, label: "Status", value: "status" },
  { icon: Target, label: "Progress", value: "progress" },
] as const satisfies readonly SortOption<CampaignSortField>[];

function option(value: string): { label: string; value: string } {
  return { label: formatCampaignEnum(value), value };
}

export {
  CAMPAIGN_CHANNELS,
  CAMPAIGN_FILTER_SCHEMA,
  CAMPAIGN_SORT_OPTIONS,
  CAMPAIGN_STATUSES,
};
