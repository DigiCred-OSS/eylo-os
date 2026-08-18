import type {
  SwarmFormMode,
  SwarmFormValues,
} from "@/features/swarms/swarms.types";

interface SwarmDraftContext {
  memberKey: string;
  mode: SwarmFormMode;
  organizationId: string;
  swarmId: string | null;
}

interface StoredSwarmDraft {
  savedAt: string;
  values: SwarmFormValues;
  version: 1;
}

class SwarmDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  clear(context: SwarmDraftContext): void {
    try {
      this.storage.removeItem(buildKey(context));
    } catch {
      // Draft cleanup is secondary to the canonical Swarm mutation.
    }
  }

  read(context: SwarmDraftContext): StoredSwarmDraft | null {
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

  write(context: SwarmDraftContext, draft: StoredSwarmDraft): boolean {
    try {
      this.storage.setItem(buildKey(context), JSON.stringify(draft));
      return true;
    } catch {
      return false;
    }
  }
}

function buildKey(context: SwarmDraftContext): string {
  return [
    "eylo.swarm-draft.v1",
    encodeURIComponent(context.memberKey.toLocaleLowerCase()),
    context.organizationId,
    context.mode,
    context.swarmId ?? "new",
  ].join(":");
}

function parseDraft(value: unknown): StoredSwarmDraft | null {
  if (
    !isRecord(value) ||
    value.version !== 1 ||
    typeof value.savedAt !== "string" ||
    Number.isNaN(new Date(value.savedAt).getTime()) ||
    !isRecord(value.values) ||
    typeof value.values.name !== "string" ||
    value.values.name.length > 100 ||
    typeof value.values.description !== "string" ||
    value.values.description.length > 2_000
  ) {
    return null;
  }
  return {
    savedAt: value.savedAt,
    values: {
      description: value.values.description,
      name: value.values.name,
    },
    version: 1,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export { SwarmDraftStorage };
export type { StoredSwarmDraft, SwarmDraftContext };
