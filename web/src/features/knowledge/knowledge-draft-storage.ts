import {
  KNOWLEDGE_CHUNKING_STRATEGIES,
  KNOWLEDGE_SCOPES,
  KNOWLEDGE_VENDORS,
  type KnowledgebaseFormMode,
  type KnowledgebaseFormValues,
} from "@/features/knowledge/knowledge.types";

interface KnowledgeDraftContext {
  knowledgebaseId: string | null;
  memberKey: string;
  mode: KnowledgebaseFormMode;
  organizationId: string;
}

interface StoredKnowledgeDraft {
  savedAt: string;
  values: KnowledgebaseFormValues;
  version: 1;
}

class KnowledgeDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  clear(context: KnowledgeDraftContext): void {
    try {
      this.storage.removeItem(buildDraftKey(context));
    } catch {
      // Draft cleanup is secondary to the canonical Knowledge mutation.
    }
  }

  read(context: KnowledgeDraftContext): StoredKnowledgeDraft | null {
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

  write(context: KnowledgeDraftContext, draft: StoredKnowledgeDraft): boolean {
    try {
      this.storage.setItem(buildDraftKey(context), JSON.stringify(draft));
      return true;
    } catch {
      return false;
    }
  }
}

function buildDraftKey(context: KnowledgeDraftContext): string {
  return [
    "eylo.knowledgebase-draft.v1",
    encodeURIComponent(context.memberKey.toLowerCase()),
    context.organizationId,
    context.mode,
    context.knowledgebaseId ?? "new",
  ].join(":");
}

function parseStoredDraft(value: unknown): StoredKnowledgeDraft | null {
  if (!isRecord(value) || value.version !== 1) {
    return null;
  }
  const savedAt = parseDate(value.savedAt);
  const values = parseValues(value.values);
  return savedAt === null || values === null
    ? null
    : { savedAt, values, version: 1 };
}

function parseValues(value: unknown): KnowledgebaseFormValues | null {
  if (!isRecord(value)) {
    return null;
  }
  const name = boundedString(value.name, 128);
  const scopeId = boundedString(value.scopeId, 100);
  const chunkSize = boundedString(value.chunkSize, 10);
  const chunkOverlap = boundedString(value.chunkOverlap, 10);
  const embeddingProviderConfigId = nullableBoundedString(
    value.embeddingProviderConfigId,
    100,
  );
  const vendor = KNOWLEDGE_VENDORS.includes(
    value.vendor as (typeof KNOWLEDGE_VENDORS)[number],
  )
    ? (value.vendor as KnowledgebaseFormValues["vendor"])
    : value.vendor === ""
      ? ""
      : null;
  const scope = KNOWLEDGE_SCOPES.includes(
    value.scope as (typeof KNOWLEDGE_SCOPES)[number],
  )
    ? (value.scope as KnowledgebaseFormValues["scope"])
    : value.scope === ""
      ? ""
      : null;
  const chunking = KNOWLEDGE_CHUNKING_STRATEGIES.includes(
    value.chunking as (typeof KNOWLEDGE_CHUNKING_STRATEGIES)[number],
  )
    ? (value.chunking as KnowledgebaseFormValues["chunking"])
    : null;

  if (
    name === null ||
    scopeId === null ||
    chunkSize === null ||
    chunkOverlap === null ||
    embeddingProviderConfigId === undefined ||
    vendor === null ||
    scope === null ||
    chunking === null ||
    typeof value.writable !== "boolean"
  ) {
    return null;
  }

  return {
    chunkOverlap,
    chunkSize,
    chunking,
    embeddingProviderConfigId,
    name,
    scope,
    scopeId,
    vendor,
    writable: value.writable,
  };
}

function boundedString(value: unknown, maximum: number): string | null {
  return typeof value === "string" && value.length <= maximum ? value : null;
}

function nullableBoundedString(
  value: unknown,
  maximum: number,
): string | null | undefined {
  return value === null ? null : (boundedString(value, maximum) ?? undefined);
}

function parseDate(value: unknown): string | null {
  return typeof value === "string" && !Number.isNaN(new Date(value).getTime())
    ? value
    : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export { KnowledgeDraftStorage };
export type { KnowledgeDraftContext, StoredKnowledgeDraft };
