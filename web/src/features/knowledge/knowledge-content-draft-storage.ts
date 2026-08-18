interface KnowledgeContentDraftContext {
  knowledgebaseId: string;
  memberKey: string;
  organizationId: string;
}

interface InlineContentDraftValues {
  content: string;
  sourceUri: string;
  title: string;
}

interface CorpusImportDraftValues {
  prefix: string;
  storageProviderConfigId: string | null;
}

interface StoredContentDraft<Values> {
  savedAt: string;
  values: Values;
  version: 1;
}

class KnowledgeContentDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  clearInline(context: KnowledgeContentDraftContext): void {
    this.remove(buildKey(context, "inline"));
  }

  clearCorpus(context: KnowledgeContentDraftContext): void {
    this.remove(buildKey(context, "corpus"));
  }

  readInline(
    context: KnowledgeContentDraftContext,
  ): StoredContentDraft<InlineContentDraftValues> | null {
    return this.read(
      buildKey(context, "inline"),
      parseInlineContentDraftValues,
    );
  }

  readCorpus(
    context: KnowledgeContentDraftContext,
  ): StoredContentDraft<CorpusImportDraftValues> | null {
    return this.read(buildKey(context, "corpus"), parseCorpusImportDraftValues);
  }

  writeInline(
    context: KnowledgeContentDraftContext,
    draft: StoredContentDraft<InlineContentDraftValues>,
  ): boolean {
    return this.write(buildKey(context, "inline"), draft);
  }

  writeCorpus(
    context: KnowledgeContentDraftContext,
    draft: StoredContentDraft<CorpusImportDraftValues>,
  ): boolean {
    return this.write(buildKey(context, "corpus"), draft);
  }

  private read<Values>(
    key: string,
    parseValues: (value: unknown) => Values | null,
  ): StoredContentDraft<Values> | null {
    try {
      const serialized = this.storage.getItem(key);
      if (serialized === null) {
        return null;
      }
      const raw: unknown = JSON.parse(serialized);
      if (!isRecord(raw) || raw.version !== 1) {
        this.remove(key);
        return null;
      }
      const savedAt = parseDate(raw.savedAt);
      const values = parseValues(raw.values);
      if (savedAt === null || values === null) {
        this.remove(key);
        return null;
      }
      return { savedAt, values, version: 1 };
    } catch {
      this.remove(key);
      return null;
    }
  }

  private write<Values>(
    key: string,
    draft: StoredContentDraft<Values>,
  ): boolean {
    try {
      this.storage.setItem(key, JSON.stringify(draft));
      return true;
    } catch {
      return false;
    }
  }

  private remove(key: string): void {
    try {
      this.storage.removeItem(key);
    } catch {
      // Draft cleanup must not change accepted durable work.
    }
  }
}

function buildKey(
  context: KnowledgeContentDraftContext,
  kind: "corpus" | "inline",
): string {
  return [
    "eylo.knowledge-content-draft.v1",
    encodeURIComponent(context.memberKey.toLowerCase()),
    context.organizationId,
    context.knowledgebaseId,
    kind,
  ].join(":");
}

function parseInlineContentDraftValues(
  value: unknown,
): InlineContentDraftValues | null {
  if (!isRecord(value)) {
    return null;
  }
  const content = boundedString(value.content, 1_000_000);
  const sourceUri = boundedString(value.sourceUri, 4_096);
  const title = boundedString(value.title, 512);
  return content === null || sourceUri === null || title === null
    ? null
    : { content, sourceUri, title };
}

function parseCorpusImportDraftValues(
  value: unknown,
): CorpusImportDraftValues | null {
  if (!isRecord(value)) {
    return null;
  }
  const prefix = boundedString(value.prefix, 1_024);
  const configId = nullableBoundedString(value.storageProviderConfigId, 100);
  return prefix === null || configId === undefined
    ? null
    : { prefix, storageProviderConfigId: configId };
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

export { KnowledgeContentDraftStorage };
export type {
  CorpusImportDraftValues,
  InlineContentDraftValues,
  KnowledgeContentDraftContext,
  StoredContentDraft,
};
