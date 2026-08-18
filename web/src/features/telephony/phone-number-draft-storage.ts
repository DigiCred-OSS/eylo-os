interface PhoneNumberDraft {
  configId: string;
  inboundAgentId: string;
  label: string;
  number: string;
  outboundAgentId: string;
  status: "" | "ACTIVE" | "INACTIVE";
}

const VERSION = 1;

class PhoneNumberDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  read(
    organizationId: string,
    numberId: string | null,
  ): PhoneNumberDraft | null {
    try {
      const raw = this.storage.getItem(key(organizationId, numberId));
      if (raw === null) return null;
      const value = JSON.parse(raw) as { draft?: unknown; version?: unknown };
      return value.version === VERSION && isDraft(value.draft)
        ? value.draft
        : null;
    } catch {
      return null;
    }
  }

  write(
    organizationId: string,
    numberId: string | null,
    draft: PhoneNumberDraft,
  ): void {
    try {
      this.storage.setItem(
        key(organizationId, numberId),
        JSON.stringify({ draft, version: VERSION }),
      );
    } catch {
      // Draft persistence is helpful, not authoritative. The visible form remains usable.
    }
  }

  clear(organizationId: string, numberId: string | null): void {
    try {
      this.storage.removeItem(key(organizationId, numberId));
    } catch {
      // A completed save must not fail because local storage is unavailable.
    }
  }
}

function key(organizationId: string, numberId: string | null): string {
  return `eylo:phone-number-draft:v${VERSION}:${organizationId}:${numberId ?? "new"}`;
}

function isDraft(value: unknown): value is PhoneNumberDraft {
  if (typeof value !== "object" || value === null) return false;
  const draft = value as Record<string, unknown>;
  return [
    "configId",
    "inboundAgentId",
    "label",
    "number",
    "outboundAgentId",
    "status",
  ].every((field) => typeof draft[field] === "string");
}

export { PhoneNumberDraftStorage, type PhoneNumberDraft };
