import type { CampaignFormValues } from "@/features/campaigns/campaigns.types";

const VERSION = 1;

class CampaignDraftStorage {
  private readonly storage: Storage;
  constructor(storage: Storage) {
    this.storage = storage;
  }
  read(scope: string, campaignId: string | null): CampaignFormValues | null {
    try {
      const raw = this.storage.getItem(key(scope, campaignId));
      if (raw === null) return null;
      const parsed = JSON.parse(raw) as { draft?: unknown; version?: unknown };
      return parsed.version === VERSION && isDraft(parsed.draft)
        ? parsed.draft
        : null;
    } catch {
      return null;
    }
  }
  write(
    scope: string,
    campaignId: string | null,
    draft: CampaignFormValues,
  ): void {
    try {
      this.storage.setItem(
        key(scope, campaignId),
        JSON.stringify({ draft, version: VERSION }),
      );
    } catch {
      /* Visible state remains authoritative while this page is open. */
    }
  }
  clear(scope: string, campaignId: string | null): void {
    try {
      this.storage.removeItem(key(scope, campaignId));
    } catch {
      /* Completion must not depend on browser storage. */
    }
  }
}

function key(scope: string, campaignId: string | null): string {
  return `eylo:campaign-draft:v${VERSION}:${scope}:${campaignId ?? "new"}`;
}
function isDraft(value: unknown): value is CampaignFormValues {
  if (typeof value !== "object" || value === null) return false;
  const draft = value as Record<string, unknown>;
  return [
    "agentId",
    "channel",
    "concurrencyLimit",
    "description",
    "emailBodyTemplate",
    "emailConfigId",
    "emailSubjectTemplate",
    "initialMessageTemplateId",
    "name",
    "retryBackoffSeconds",
    "retryMaxRetries",
    "retryOn",
  ].every((field) => typeof draft[field] === "string");
}

export { CampaignDraftStorage };
