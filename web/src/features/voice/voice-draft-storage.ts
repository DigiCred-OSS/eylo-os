import { parseVoiceConfigFormValues } from "@/features/voice/voice-form-values";
import type {
  StoredVoiceConfigDraft,
  VoiceConfigDraftContext,
} from "@/features/voice/voice.types";

class VoiceConfigDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  clear(context: VoiceConfigDraftContext): void {
    try {
      this.storage.removeItem(buildDraftKey(context));
    } catch {
      // Draft cleanup is secondary to the canonical Voice Config mutation.
    }
  }

  read(context: VoiceConfigDraftContext): StoredVoiceConfigDraft | null {
    try {
      const serialized = this.storage.getItem(buildDraftKey(context));
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
    context: VoiceConfigDraftContext,
    draft: StoredVoiceConfigDraft,
  ): boolean {
    try {
      this.storage.setItem(buildDraftKey(context), JSON.stringify(draft));
      return true;
    } catch {
      return false;
    }
  }
}

function buildDraftKey(context: VoiceConfigDraftContext): string {
  return [
    "eylo.voice-config-draft.v1",
    encodeURIComponent(context.memberKey.toLowerCase()),
    context.organizationId,
    context.mode,
    context.voiceConfigId ?? "new",
  ].join(":");
}

function parseStoredDraft(value: unknown): StoredVoiceConfigDraft | null {
  if (!isRecord(value) || value.version !== 1) {
    return null;
  }
  const baseRevision = parseBaseRevision(value.baseRevision);
  const savedAt = parseDate(value.savedAt);
  const values = parseVoiceConfigFormValues(value.values);
  if (baseRevision === undefined || savedAt === null || values === null) {
    return null;
  }
  return { baseRevision, savedAt, values, version: 1 };
}

function parseBaseRevision(value: unknown): number | null | undefined {
  if (value === null) {
    return null;
  }
  return Number.isSafeInteger(value) && Number(value) > 0
    ? Number(value)
    : undefined;
}

function parseDate(value: unknown): string | null {
  return typeof value === "string" && !Number.isNaN(new Date(value).getTime())
    ? value
    : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export { VoiceConfigDraftStorage };
