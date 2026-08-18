import type { ScheduleFormValues } from "@/features/automations/automations.types";

interface StoredAutomationDraft {
  savedAt: string;
  values: ScheduleFormValues;
  version: 1;
}

class AutomationDraftStorage {
  private readonly storage: Storage;

  constructor(storage: Storage) {
    this.storage = storage;
  }

  load(key: string): StoredAutomationDraft | null {
    try {
      const raw = this.storage.getItem(key);
      if (raw === null) return null;
      const parsed = JSON.parse(raw) as Partial<StoredAutomationDraft>;
      if (
        parsed.version !== 1 ||
        typeof parsed.values !== "object" ||
        parsed.values === null
      )
        return null;
      return parsed as StoredAutomationDraft;
    } catch {
      return null;
    }
  }

  save(key: string, values: ScheduleFormValues): void {
    this.storage.setItem(
      key,
      JSON.stringify({
        savedAt: new Date().toISOString(),
        values,
        version: 1,
      } satisfies StoredAutomationDraft),
    );
  }

  clear(key: string): void {
    this.storage.removeItem(key);
  }
}

function automationDraftKey(
  organizationId: string,
  memberId: string,
  mode: "create" | "edit",
  scheduleId: string | undefined,
): string {
  return `eylo.automation-draft.v1:${organizationId}:${memberId}:${mode}:${scheduleId ?? "new"}`;
}

export { AutomationDraftStorage, automationDraftKey };
