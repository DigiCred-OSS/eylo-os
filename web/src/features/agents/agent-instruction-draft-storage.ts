interface AgentInstructionDraftContext {
  memberKey: string;
  organizationId: string;
  templateId: string | null;
}

interface StoredAgentInstructionDraft {
  baseDraftVersion: number | null;
  body: string;
  name: string;
  savedAt: string;
  version: 1;
}

class AgentInstructionDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  clear(context: AgentInstructionDraftContext): void {
    try {
      this.storage.removeItem(buildDraftKey(context));
    } catch {
      // Instruction recovery is secondary to the template API lifecycle.
    }
  }

  read(
    context: AgentInstructionDraftContext,
  ): StoredAgentInstructionDraft | null {
    try {
      const serialized = this.storage.getItem(buildDraftKey(context));
      if (serialized === null) {
        return null;
      }
      const parsed = parseStoredDraft(JSON.parse(serialized) as unknown);
      if (parsed === null) {
        this.clear(context);
      }
      return parsed;
    } catch {
      this.clear(context);
      return null;
    }
  }

  write(
    context: AgentInstructionDraftContext,
    draft: StoredAgentInstructionDraft,
  ): boolean {
    try {
      this.storage.setItem(buildDraftKey(context), JSON.stringify(draft));
      return true;
    } catch {
      return false;
    }
  }
}

function buildDraftKey(context: AgentInstructionDraftContext): string {
  return [
    "eylo.agent-instructions-draft.v1",
    encodeURIComponent(context.memberKey.toLowerCase()),
    context.organizationId,
    context.templateId ?? "new",
  ].join(":");
}

function parseStoredDraft(value: unknown): StoredAgentInstructionDraft | null {
  if (!isRecord(value) || value.version !== 1) {
    return null;
  }
  const baseDraftVersion = parseDraftVersion(value.baseDraftVersion);
  const body = parseText(value.body, 64_000);
  const name = parseText(value.name, 128);
  const savedAt = parseDate(value.savedAt);
  if (
    baseDraftVersion === undefined ||
    body === null ||
    name === null ||
    savedAt === null
  ) {
    return null;
  }
  return { baseDraftVersion, body, name, savedAt, version: 1 };
}

function parseDraftVersion(value: unknown): number | null | undefined {
  if (value === null) {
    return null;
  }
  return Number.isSafeInteger(value) && Number(value) > 0
    ? Number(value)
    : undefined;
}

function parseText(value: unknown, maximum: number): string | null {
  return typeof value === "string" && value.length <= maximum ? value : null;
}

function parseDate(value: unknown): string | null {
  return typeof value === "string" && !Number.isNaN(new Date(value).getTime())
    ? value
    : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export { AgentInstructionDraftStorage };
export type { AgentInstructionDraftContext, StoredAgentInstructionDraft };
