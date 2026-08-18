import type {
  Campaign,
  CampaignChannel,
  CampaignCreate,
  CampaignFormValues,
  CampaignUpdate,
} from "@/features/campaigns/campaigns.types";

const EMPTY_CAMPAIGN_FORM: CampaignFormValues = {
  agentId: "",
  channel: "",
  concurrencyLimit: "",
  description: "",
  emailBodyTemplate: "",
  emailConfigId: "",
  emailSubjectTemplate: "",
  initialMessageTemplateId: "",
  name: "",
  retryBackoffSeconds: "",
  retryMaxRetries: "",
  retryOn: "",
};

function campaignToForm(campaign: Campaign): CampaignFormValues {
  const config = campaign.channelConfig;
  const retry = campaign.retryPolicy;
  return {
    agentId: campaign.agentId,
    channel: isChannel(campaign.channel) ? campaign.channel : "",
    concurrencyLimit: String(campaign.concurrencyLimit),
    description: campaign.description ?? "",
    emailBodyTemplate: stringValue(config.body_template),
    emailConfigId: stringValue(config.provider_config_id),
    emailSubjectTemplate: stringValue(config.subject_template),
    initialMessageTemplateId: campaign.initialMessageTemplateId ?? "",
    name: campaign.name,
    retryBackoffSeconds: numberString(retry.backoff_seconds),
    retryMaxRetries: numberString(retry.max_retries),
    retryOn: Array.isArray(retry.retry_on)
      ? retry.retry_on
          .filter((item): item is string => typeof item === "string")
          .join(", ")
      : "",
  };
}

function validateCampaignForm(
  values: CampaignFormValues,
  readyEmailConfigIds: ReadonlySet<string>,
): Partial<Record<keyof CampaignFormValues, string>> {
  const errors: Partial<Record<keyof CampaignFormValues, string>> = {};
  if (values.name.trim() === "") errors.name = "Name is required.";
  if (values.name.trim().length > 256)
    errors.name = "Name must be 256 characters or fewer.";
  if (values.channel === "") errors.channel = "Choose an outreach channel.";
  if (values.agentId === "") errors.agentId = "Choose a published Agent.";
  if (!positiveInteger(values.concurrencyLimit, 50))
    errors.concurrencyLimit =
      "Concurrency must be a whole number from 1 to 50.";
  if (!nonNegativeInteger(values.retryMaxRetries))
    errors.retryMaxRetries =
      "Maximum retries must be a non-negative whole number.";
  if (!nonNegativeInteger(values.retryBackoffSeconds))
    errors.retryBackoffSeconds =
      "Backoff must be a non-negative number of seconds.";
  if (values.channel === "email") {
    if (!readyEmailConfigIds.has(values.emailConfigId))
      errors.emailConfigId = "Choose a ready email configuration.";
    if (values.emailSubjectTemplate.trim() === "")
      errors.emailSubjectTemplate = "Email subject is required.";
    if (values.emailBodyTemplate.trim() === "")
      errors.emailBodyTemplate = "Email body is required.";
  }
  if (values.channel === "widget" && values.initialMessageTemplateId === "")
    errors.initialMessageTemplateId =
      "Widget campaigns require a published initial message template.";
  return errors;
}

function toCampaignCreate(values: CampaignFormValues): CampaignCreate {
  const channel = values.channel as CampaignChannel;
  return {
    agentId: values.agentId,
    channel,
    channelConfig: channelConfig(values, channel),
    concurrencyLimit: Number(values.concurrencyLimit),
    description: optional(values.description),
    initialMessageTemplateId:
      channel === "email" ? null : optional(values.initialMessageTemplateId),
    name: values.name.trim(),
    retryPolicy: retryPolicy(values),
  };
}

function toCampaignUpdate(
  values: CampaignFormValues,
  expectedRevision: number,
): CampaignUpdate {
  const create = toCampaignCreate(values);
  return { ...create, expectedRevision };
}

function channelConfig(
  values: CampaignFormValues,
  channel: CampaignChannel,
): Record<string, unknown> {
  if (channel !== "email") return {};
  return {
    body_template: values.emailBodyTemplate,
    provider_config_id: values.emailConfigId,
    subject_template: values.emailSubjectTemplate,
  };
}

function retryPolicy(values: CampaignFormValues): Record<string, unknown> {
  return {
    backoff_seconds: Number(values.retryBackoffSeconds),
    max_retries: Number(values.retryMaxRetries),
    retry_on: values.retryOn
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  };
}

function optional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}
function isChannel(value: string): value is CampaignChannel {
  return value === "voice" || value === "email" || value === "widget";
}
function positiveInteger(value: string, max: number): boolean {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= max;
}
function nonNegativeInteger(value: string): boolean {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0;
}
function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}
function numberString(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value)
    ? String(value)
    : "";
}

export {
  campaignToForm,
  EMPTY_CAMPAIGN_FORM,
  toCampaignCreate,
  toCampaignUpdate,
  validateCampaignForm,
};
