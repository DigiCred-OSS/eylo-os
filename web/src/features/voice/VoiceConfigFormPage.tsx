import { ArrowLeft, Check, RotateCcw, Save } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useState } from "react";
import {
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";
import { VoiceConfigEditorFields } from "@/features/voice/VoiceConfigEditorFields";
import { formatVoiceDate } from "@/features/voice/voice-formatters";
import type {
  VoiceConfigFormMode,
  VoiceConfigFormSection,
} from "@/features/voice/voice.types";
import { cn } from "@/lib/utils";
import { useAsyncContextGuard } from "@/lib/use-async-context-guard";

const FORM_SECTIONS: readonly {
  description: string;
  id: VoiceConfigFormSection;
  label: string;
}[] = [
  { description: "Name and purpose", id: "identity", label: "Identity" },
  { description: "STT, TTS, or realtime", id: "runtime", label: "Runtime" },
  {
    description: "Greeting and call limits",
    id: "conversation",
    label: "Conversation",
  },
  {
    description: "Turns, interruption, silence",
    id: "interaction",
    label: "Interaction",
  },
  {
    description: "Recording and post-call data",
    id: "data",
    label: "Data",
  },
  {
    description: "Metrics and provider latency",
    id: "observability",
    label: "Observability",
  },
];

const VoiceConfigFormPage = observer(function VoiceConfigFormPage({
  mode,
}: {
  mode: VoiceConfigFormMode;
}) {
  const { auth, voice } = useRootStore();
  const form = voice.form;
  const member = auth.member;
  const { organizationId, voiceConfigId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const section = parseSection(searchParams.get("section"));
  const contextKey = `${organizationId ?? "missing"}:${mode}:${voiceConfigId ?? "new"}`;
  const isCurrentContext = useAsyncContextGuard(contextKey);

  useEffect(() => {
    if (member === null || organizationId === undefined) {
      return;
    }
    if (mode === "create") {
      form.beginCreate({ memberKey: member.email, organizationId });
    } else if (voiceConfigId !== undefined) {
      void form.beginEdit({
        memberKey: member.email,
        organizationId,
        voiceConfigId,
      });
    }
  }, [form, member, mode, organizationId, voiceConfigId]);

  if (member === null || organizationId === undefined) {
    return null;
  }
  const isExpectedRoute =
    (mode === "create" && voiceConfigId === undefined) ||
    (mode === "edit" && voiceConfigId !== undefined);
  if (!isExpectedRoute) {
    return null;
  }

  function updateSection(nextSection: VoiceConfigFormSection): void {
    const nextParams = new URLSearchParams(searchParams);
    if (nextSection === "identity") {
      nextParams.delete("section");
    } else {
      nextParams.set("section", nextSection);
    }
    setSearchParams(nextParams);
  }

  function returnToCollection(): void {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("section");
    const search = nextParams.toString();
    void navigate({
      pathname: `/org/${organizationId}/voice`,
      search: search === "" ? "" : `?${search}`,
    });
  }

  async function submit(): Promise<void> {
    const submittedContextKey = contextKey;
    const saved = await form.submit();
    if (saved === null) {
      const errorSection = inferErrorSection(form.errorMessage);
      if (errorSection !== null && errorSection !== section) {
        updateSection(errorSection);
      }
      return;
    }
    if (!isCurrentContext(submittedContextKey)) {
      return;
    }
    voice.upsert(saved);
    setSavedNotice("Voice Config saved to Eylo.");
    if (mode === "create") {
      void navigate(
        {
          pathname: `/org/${organizationId}/voice/${saved.id}/edit`,
          search: location.search,
        },
        { replace: true },
      );
    }
  }

  const draftDate =
    form.savedAt === null ? null : formatVoiceDate(form.savedAt).label;
  return (
    <section
      className="min-h-[calc(100svh-3.5rem)]"
      aria-labelledby="voice-config-form-title"
    >
      <header className="sticky top-14 z-10 flex min-h-16 flex-wrap items-center justify-between gap-3 border-b bg-background/95 px-4 py-3 backdrop-blur sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Back to Voice"
            title="Back to Voice"
            onClick={returnToCollection}
          >
            <ArrowLeft aria-hidden="true" />
          </Button>
          <div className="min-w-0">
            <h1
              id="voice-config-form-title"
              className="truncate text-lg font-semibold tracking-tight"
            >
              {mode === "create"
                ? "New Voice Config"
                : form.serverVoiceConfig?.name || "Edit Voice Config"}
            </h1>
            <p className="truncate text-xs text-muted-foreground">
              {form.hasLocalDraft && draftDate !== null
                ? `Draft saved locally ${draftDate}`
                : form.isDirty
                  ? "Saving local draft…"
                  : "No unsaved local changes"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {form.hasLocalDraft ? (
            <Button
              variant="outline"
              disabled={form.isSubmitting}
              onClick={() => {
                setSavedNotice(null);
                form.discardLocalDraft();
              }}
            >
              <RotateCcw aria-hidden="true" />
              {mode === "create" ? "Start new" : "Discard draft"}
            </Button>
          ) : null}
          <Button
            type="submit"
            form="voice-config-form"
            disabled={
              form.isLoading ||
              form.isSubmitting ||
              form.conflictMessage !== null ||
              (mode === "edit" &&
                (form.serverVoiceConfig === null || !form.isDirty))
            }
          >
            <Save aria-hidden="true" />
            {form.isSubmitting ? "Saving…" : "Save Voice Config"}
          </Button>
        </div>
      </header>

      <div className="grid lg:grid-cols-[15rem_minmax(0,48rem)] lg:justify-center lg:gap-10 lg:px-6">
        <nav
          className="flex gap-1 overflow-x-auto border-b p-3 lg:sticky lg:top-30 lg:block lg:h-fit lg:border-b-0 lg:p-6 lg:pr-0"
          aria-label="Voice Config form sections"
        >
          {FORM_SECTIONS.map((formSection) => (
            <button
              key={formSection.id}
              className={cn(
                "min-w-fit rounded-md px-3 py-2 text-left text-sm transition-colors lg:block lg:w-full",
                section === formSection.id
                  ? "bg-muted font-medium text-foreground"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
              )}
              type="button"
              aria-current={section === formSection.id ? "step" : undefined}
              onClick={() => updateSection(formSection.id)}
            >
              <span className="block">{formSection.label}</span>
              <span className="mt-0.5 hidden text-xs font-normal text-muted-foreground lg:block">
                {formSection.description}
              </span>
            </button>
          ))}
        </nav>

        <div className="space-y-5 p-4 sm:p-6 lg:px-0 lg:py-8">
          <FormMessages
            conflictMessage={form.conflictMessage}
            draftStorageErrorMessage={form.draftStorageErrorMessage}
            errorMessage={form.errorMessage}
            readinessMessage={form.readinessMessage}
            savedNotice={!form.isDirty ? savedNotice : null}
            onKeepLocal={form.keepLocalChanges}
            onUseServer={form.useServerVersion}
          />

          {form.isLoading ? (
            <div className="border p-8 text-center text-sm text-muted-foreground">
              Loading Voice Config…
            </div>
          ) : form.errorMessage !== null &&
            form.serverVoiceConfig === null &&
            mode === "edit" ? (
            <div className="border p-8 text-center">
              <p className="text-sm text-destructive">{form.errorMessage}</p>
              <Button
                className="mt-4"
                variant="outline"
                onClick={returnToCollection}
              >
                Back to Voice
              </Button>
            </div>
          ) : (
            <form
              id="voice-config-form"
              onSubmit={(event) => {
                event.preventDefault();
                void submit();
              }}
            >
              <fieldset
                className="min-w-0 border-0 p-0"
                disabled={form.isSubmitting}
              >
                <VoiceConfigEditorFields
                  form={form}
                  organizationId={organizationId}
                  section={section}
                />
              </fieldset>
            </form>
          )}
        </div>
      </div>
    </section>
  );
});

function FormMessages({
  conflictMessage,
  draftStorageErrorMessage,
  errorMessage,
  onKeepLocal,
  onUseServer,
  readinessMessage,
  savedNotice,
}: {
  conflictMessage: string | null;
  draftStorageErrorMessage: string | null;
  errorMessage: string | null;
  onKeepLocal: () => void;
  onUseServer: () => void;
  readinessMessage: string | null;
  savedNotice: string | null;
}) {
  return (
    <div className="space-y-3" aria-live="polite">
      {conflictMessage === null ? null : (
        <div className="border bg-muted/30 p-4" role="alert">
          <p className="text-sm font-medium">Revision conflict</p>
          <p className="mt-1 text-sm leading-5">{conflictMessage}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={onKeepLocal}>
              Keep my changes
            </Button>
            <Button type="button" variant="ghost" onClick={onUseServer}>
              Use latest saved version
            </Button>
          </div>
        </div>
      )}
      {draftStorageErrorMessage === null ? null : (
        <div
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          role="alert"
        >
          {draftStorageErrorMessage}
        </div>
      )}
      {errorMessage === null ? null : (
        <div
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          role="alert"
        >
          {errorMessage}
        </div>
      )}
      {readinessMessage === null ? null : (
        <div className="border bg-muted/30 p-3 text-sm text-muted-foreground">
          Draft readiness: {readinessMessage}
        </div>
      )}
      {savedNotice === null ? null : (
        <div
          className="flex items-center gap-2 border p-3 text-sm"
          role="status"
        >
          <Check className="size-4" aria-hidden="true" />
          {savedNotice}
        </div>
      )}
    </div>
  );
}

function parseSection(value: string | null): VoiceConfigFormSection {
  return FORM_SECTIONS.some((section) => section.id === value)
    ? (value as VoiceConfigFormSection)
    : "identity";
}

function inferErrorSection(
  errorMessage: string | null,
): VoiceConfigFormSection | null {
  if (errorMessage === null) {
    return null;
  }
  if (
    errorMessage.startsWith("Name") ||
    errorMessage.startsWith("Description")
  ) {
    return "identity";
  }
  if (errorMessage.includes("recording notification")) {
    return "data";
  }
  if (errorMessage.includes("silence reminder")) {
    return "interaction";
  }
  return null;
}

export { VoiceConfigFormPage };
