import type {
  ProviderDraftContext,
  ProviderFieldDefinition,
  ProviderFieldValue,
  ProviderFormValues,
  StoredProviderDraft,
} from "@/features/providers/providers.types";

class ProviderDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  clear(context: ProviderDraftContext): void {
    try {
      this.storage.removeItem(buildDraftKey(context));
    } catch {
      // Draft cleanup is secondary to the provider configuration lifecycle.
    }
  }

  read(context: ProviderDraftContext): StoredProviderDraft | null {
    const key = buildDraftKey(context);
    try {
      const serialized = this.storage.getItem(key);
      if (serialized === null) {
        return null;
      }
      const draft = parseStoredDraft(JSON.parse(serialized) as unknown);
      if (draft === null) {
        this.clear(context);
      }
      return draft;
    } catch {
      this.clear(context);
      return null;
    }
  }

  write(
    context: ProviderDraftContext,
    draft: StoredProviderDraft,
    fields: readonly ProviderFieldDefinition[],
  ): boolean {
    const safeDraft: StoredProviderDraft = {
      ...draft,
      values: withoutSecretFields(draft.values, fields),
    };

    try {
      this.storage.setItem(buildDraftKey(context), JSON.stringify(safeDraft));
      return true;
    } catch {
      return false;
    }
  }
}

function withoutSecretFields(
  values: ProviderFormValues,
  fields: readonly ProviderFieldDefinition[],
): ProviderFormValues {
  const allowedKeys = new Set(
    fields
      .filter((field) => field.target === "config" && !field.secret)
      .map((field) => field.key),
  );
  return {
    config: Object.fromEntries(
      Object.entries(values.config).filter(([key]) => allowedKeys.has(key)),
    ),
    name: values.name,
    provider: values.provider,
  };
}

function buildDraftKey(context: ProviderDraftContext): string {
  return [
    "eylo.provider-draft.v1",
    encodeURIComponent(context.memberKey.toLowerCase()),
    context.organizationId,
    context.capability,
    context.configId ?? "new",
  ].join(":");
}

function parseStoredDraft(value: unknown): StoredProviderDraft | null {
  if (!isRecord(value) || value.version !== 1) {
    return null;
  }
  const savedAt = parseDate(value.savedAt);
  const values = parseFormValues(value.values);
  if (savedAt === null || values === null) {
    return null;
  }
  return { savedAt, values, version: 1 };
}

function parseFormValues(value: unknown): ProviderFormValues | null {
  if (!isRecord(value) || !isRecord(value.config)) {
    return null;
  }
  const name = parseText(value.name, 100);
  const provider = parseText(value.provider, 100);
  const entries = Object.entries(value.config);
  if (name === null || provider === null || entries.length > 300) {
    return null;
  }

  const config: Record<string, ProviderFieldValue> = {};
  for (const [key, rawValue] of entries) {
    const parsed = parseFieldValue(rawValue);
    if (key.length > 100 || parsed === undefined) {
      return null;
    }
    config[key] = parsed;
  }
  return { config, name, provider };
}

function parseFieldValue(value: unknown): ProviderFieldValue | undefined {
  if (value === null || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    return value.length <= 20_000 ? value : undefined;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : undefined;
  }
  if (
    Array.isArray(value) &&
    value.length <= 100 &&
    value.every((item) => typeof item === "string" && item.length <= 1_000)
  ) {
    return value;
  }
  return undefined;
}

function parseDate(value: unknown): string | null {
  return typeof value === "string" && !Number.isNaN(new Date(value).getTime())
    ? value
    : null;
}

function parseText(value: unknown, maximum: number): string | null {
  return typeof value === "string" && value.length <= maximum ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export { ProviderDraftStorage };
