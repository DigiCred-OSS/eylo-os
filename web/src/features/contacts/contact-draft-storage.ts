import type {
  ContactFormMode,
  ContactFormValues,
} from "@/features/contacts/contacts.types";

interface ContactDraftContext {
  contactId: string | null;
  memberKey: string;
  mode: ContactFormMode;
  organizationId: string;
}

interface StoredContactDraft {
  savedAt: string;
  values: ContactFormValues;
  version: 1;
}

class ContactDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  clear(context: ContactDraftContext): void {
    try {
      this.storage.removeItem(buildKey(context));
    } catch {
      // Draft cleanup is secondary to the canonical Contact mutation.
    }
  }

  read(context: ContactDraftContext): StoredContactDraft | null {
    try {
      const serialized = this.storage.getItem(buildKey(context));
      if (serialized === null) return null;
      const draft = parseDraft(JSON.parse(serialized) as unknown);
      if (draft === null) this.clear(context);
      return draft;
    } catch {
      this.clear(context);
      return null;
    }
  }

  write(context: ContactDraftContext, draft: StoredContactDraft): boolean {
    try {
      this.storage.setItem(buildKey(context), JSON.stringify(draft));
      return true;
    } catch {
      return false;
    }
  }
}

function buildKey(context: ContactDraftContext): string {
  return [
    "eylo.contact-draft.v1",
    encodeURIComponent(context.memberKey.toLowerCase()),
    context.organizationId,
    context.mode,
    context.contactId ?? "new",
  ].join(":");
}

function parseDraft(value: unknown): StoredContactDraft | null {
  if (
    !isRecord(value) ||
    value.version !== 1 ||
    typeof value.savedAt !== "string"
  ) {
    return null;
  }
  if (Number.isNaN(new Date(value.savedAt).getTime())) return null;
  const values = parseValues(value.values);
  return values === null
    ? null
    : { savedAt: value.savedAt, values, version: 1 };
}

function parseValues(value: unknown): ContactFormValues | null {
  if (!isRecord(value) || !isRecord(value.preferences)) return null;
  const externalId = boundedString(value.externalId, 1_000);
  const name = boundedString(value.name, 255);
  const primaryEmail = boundedString(value.primaryEmail, 320);
  const primaryPhone = boundedString(value.primaryPhone, 16);
  const entries = Object.entries(value.preferences);
  if (
    externalId === null ||
    name === null ||
    primaryEmail === null ||
    primaryPhone === null ||
    entries.length > 100 ||
    entries.some(
      ([key, item]) =>
        key.length === 0 ||
        key.length > 100 ||
        typeof item !== "string" ||
        item.length > 1_000,
    )
  ) {
    return null;
  }
  return {
    externalId,
    name,
    preferences: Object.fromEntries(entries) as Record<string, string>,
    primaryEmail,
    primaryPhone,
  };
}

function boundedString(value: unknown, maximum: number): string | null {
  return typeof value === "string" && value.length <= maximum ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export { ContactDraftStorage };
export type { ContactDraftContext, StoredContactDraft };
