import type {
  CuratedAuthKind,
  IntegrationDraftContext,
  IntegrationInstallDraftValues,
  StoredIntegrationDraft,
} from "@/features/integrations/integrations.types";

const AUTH_KINDS = [
  "no_auth",
  "api_key",
  "basic",
  "oauth2",
] as const satisfies readonly CuratedAuthKind[];

class IntegrationDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  clear(context: IntegrationDraftContext): void {
    try {
      this.storage.removeItem(buildKey(context));
    } catch {
      // Draft cleanup is secondary to the canonical installation mutation.
    }
  }

  read(context: IntegrationDraftContext): StoredIntegrationDraft | null {
    try {
      const raw = this.storage.getItem(buildKey(context));
      if (raw === null) return null;
      const parsed = parseDraft(JSON.parse(raw) as unknown);
      if (parsed === null) this.clear(context);
      return parsed;
    } catch {
      this.clear(context);
      return null;
    }
  }

  write(
    context: IntegrationDraftContext,
    values: IntegrationInstallDraftValues,
  ): boolean {
    try {
      this.storage.setItem(
        buildKey(context),
        JSON.stringify({
          savedAt: new Date().toISOString(),
          values,
          version: 1,
        }),
      );
      return true;
    } catch {
      return false;
    }
  }
}

function buildKey(context: IntegrationDraftContext): string {
  return [
    "eylo.integration-install-draft.v1",
    encodeURIComponent(context.memberKey.toLowerCase()),
    context.organizationId,
    context.vendor,
  ].join(":");
}

function parseDraft(value: unknown): StoredIntegrationDraft | null {
  if (!isRecord(value) || value.version !== 1 || !isRecord(value.values)) {
    return null;
  }
  const savedAt = boundedString(value.savedAt, 100);
  const instanceUrl = boundedString(value.values.instanceUrl, 2_000);
  const oauthClientId = boundedString(value.values.oauthClientId, 1_000);
  const oauthTenant = boundedString(value.values.oauthTenant, 1_000);
  const authKind =
    value.values.authKind === "" ||
    AUTH_KINDS.includes(value.values.authKind as CuratedAuthKind)
      ? (value.values.authKind as CuratedAuthKind | "")
      : null;
  if (
    savedAt === null ||
    instanceUrl === null ||
    oauthClientId === null ||
    oauthTenant === null ||
    authKind === null
  ) {
    return null;
  }
  return {
    savedAt,
    values: { authKind, instanceUrl, oauthClientId, oauthTenant },
    version: 1,
  };
}

function boundedString(value: unknown, maximum: number): string | null {
  return typeof value === "string" && value.length <= maximum ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export { IntegrationDraftStorage };
