import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ProviderConfigReferenceField } from "@/features/providers/ProviderConfigReferenceField";
import type { VoiceConfigFormStore } from "@/features/voice/voice-form.store";
import type {
  VoiceConfigFormSection,
  VoiceConfigFormValues,
  VoiceInterruptionType,
  VoiceRuntimeMode,
} from "@/features/voice/voice.types";

function VoiceConfigEditorFields({
  form,
  organizationId,
  section,
}: {
  form: VoiceConfigFormStore;
  organizationId: string;
  section: VoiceConfigFormSection;
}) {
  function change<Field extends keyof VoiceConfigFormValues>(
    field: Field,
    value: VoiceConfigFormValues[Field],
  ): void {
    form.setField(field, value);
  }

  if (section === "identity") {
    return (
      <EditorGroup
        title="Identity"
        description="Name this reusable organization Voice Config so teammates can assign it consistently."
      >
        <Field label="Name" htmlFor="voice-config-name" required>
          <Input
            id="voice-config-name"
            required
            maxLength={128}
            autoComplete="off"
            value={form.values.name}
            onChange={(event) => change("name", event.target.value)}
          />
        </Field>
        <Field
          label="Description"
          htmlFor="voice-config-description"
          hint="Explain the intended voice experience and where this config should be reused."
        >
          <Textarea
            id="voice-config-description"
            rows={5}
            maxLength={2_000}
            value={form.values.description}
            onChange={(event) => change("description", event.target.value)}
          />
        </Field>
      </EditorGroup>
    );
  }

  if (section === "runtime") {
    return (
      <EditorGroup
        title="Runtime"
        description="Choose one explicit voice runtime. Eylo never substitutes an unassigned provider."
      >
        <Field label="Runtime mode" htmlFor="voice-config-runtime">
          <Select
            value={form.values.runtimeMode}
            onValueChange={(value) =>
              change("runtimeMode", value as VoiceRuntimeMode)
            }
          >
            <SelectTrigger id="voice-config-runtime" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="decomposed">
                Decomposed · STT + Agent LLM + TTS
              </SelectItem>
              <SelectItem value="realtime">
                Realtime · live speech-to-speech model
              </SelectItem>
            </SelectContent>
          </Select>
        </Field>

        {form.values.runtimeMode === "decomposed" ? (
          <div className="space-y-3">
            <ProviderConfigReferenceField
              description="Transcribes caller audio for the Agent loop."
              field="sttProviderConfigId"
              label="Speech-to-text configuration"
              organizationId={organizationId}
              references={form.references}
              value={form.values.sttProviderConfigId}
              onChange={(value) => change("sttProviderConfigId", value)}
            />
            <ProviderConfigReferenceField
              description="Turns completed Agent responses into streamed audio."
              field="ttsProviderConfigId"
              label="Text-to-speech configuration"
              organizationId={organizationId}
              references={form.references}
              value={form.values.ttsProviderConfigId}
              onChange={(value) => change("ttsProviderConfigId", value)}
            />
          </div>
        ) : (
          <ProviderConfigReferenceField
            description="Owns the live model, voice, protocol settings, and credentials."
            field="realtimeProviderConfigId"
            label="Realtime configuration"
            organizationId={organizationId}
            references={form.references}
            value={form.values.realtimeProviderConfigId}
            onChange={(value) => change("realtimeProviderConfigId", value)}
          />
        )}

        <div className="border bg-muted/20 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium">Capability boundary</p>
            <Badge variant="outline">Platform-owned</Badge>
          </div>
          <p className="mt-2 text-sm leading-5 text-muted-foreground">
            Interruption, silence handling, recording, redaction, and lifecycle
            behavior are Eylo features. Provider-native support is reported in
            the Voice Config details; a missing native feature does not disable
            the platform behavior.
          </p>
        </div>
      </EditorGroup>
    );
  }

  if (section === "conversation") {
    return (
      <EditorGroup
        title="Conversation"
        description="Control how the call starts and the explicit conditions that end it."
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Opening behavior" htmlFor="voice-first-message-mode">
            <Select
              value={form.values.firstMessageMode}
              onValueChange={(value) =>
                change(
                  "firstMessageMode",
                  value as VoiceConfigFormValues["firstMessageMode"],
                )
              }
            >
              <SelectTrigger id="voice-first-message-mode">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="assistant-speaks-first">
                  Agent speaks first
                </SelectItem>
                <SelectItem value="assistant-waits">
                  Wait for the caller
                </SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <NumberField
            id="voice-max-duration"
            label="Maximum duration (seconds)"
            min={0}
            max={86_400}
            value={form.values.maxDurationSeconds}
            onChange={(value) => change("maxDurationSeconds", value)}
            hint="0 keeps the call unlimited."
          />
        </div>
        <Field label="Opening message" htmlFor="voice-first-message">
          <Textarea
            id="voice-first-message"
            rows={3}
            disabled={form.values.firstMessageMode === "assistant-waits"}
            value={form.values.firstMessage}
            placeholder="What the Agent says when the call connects"
            onChange={(event) => change("firstMessage", event.target.value)}
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="End-call message" htmlFor="voice-end-call-message">
            <Textarea
              id="voice-end-call-message"
              rows={3}
              value={form.values.endCallMessage}
              onChange={(event) => change("endCallMessage", event.target.value)}
            />
          </Field>
          <Field label="End-call phrases" htmlFor="voice-end-call-phrases">
            <Textarea
              id="voice-end-call-phrases"
              rows={3}
              value={form.values.endCallPhrases}
              placeholder="One phrase per line"
              onChange={(event) => change("endCallPhrases", event.target.value)}
            />
          </Field>
        </div>
      </EditorGroup>
    );
  }

  if (section === "interaction") {
    return (
      <EditorGroup
        title="Turn-taking and silence"
        description="Tune when the Agent starts, when caller speech interrupts it, and when an idle call ends."
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <NumberField
            id="voice-start-wait"
            label="Start wait (ms)"
            min={0}
            max={5_000}
            value={form.values.startWaitMs}
            onChange={(value) => change("startWaitMs", value)}
          />
          <NumberField
            id="voice-responsiveness"
            label="Responsiveness"
            min={0}
            max={1}
            step={0.1}
            value={form.values.startResponsiveness}
            onChange={(value) => change("startResponsiveness", value)}
          />
          <Field label="Interruption signal" htmlFor="voice-interruption-type">
            <Select
              value={form.values.interruptionType}
              onValueChange={(value) =>
                change("interruptionType", value as VoiceInterruptionType)
              }
            >
              <SelectTrigger id="voice-interruption-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="transcript">Transcript</SelectItem>
                <SelectItem value="vad">Voice activity</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <NumberField
            id="voice-interruption-words"
            label="Minimum words"
            min={0}
            max={50}
            value={form.values.numWords}
            onChange={(value) => change("numWords", value)}
          />
          <NumberField
            id="voice-interruption-backoff"
            label="Backoff (seconds)"
            min={0}
            max={10}
            step={0.1}
            value={form.values.backoffSeconds}
            onChange={(value) => change("backoffSeconds", value)}
          />
          <NumberField
            id="voice-interruption-sensitivity"
            label="Sensitivity"
            min={0}
            max={1}
            step={0.1}
            value={form.values.interruptionSensitivity}
            onChange={(value) => change("interruptionSensitivity", value)}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Acknowledgement phrases"
            htmlFor="voice-acknowledgements"
          >
            <Textarea
              id="voice-acknowledgements"
              rows={3}
              value={form.values.acknowledgementPhrases}
              placeholder="One phrase per line"
              onChange={(event) =>
                change("acknowledgementPhrases", event.target.value)
              }
            />
          </Field>
          <Field label="Interruption phrases" htmlFor="voice-interruptions">
            <Textarea
              id="voice-interruptions"
              rows={3}
              value={form.values.interruptionPhrases}
              placeholder="One phrase per line"
              onChange={(event) =>
                change("interruptionPhrases", event.target.value)
              }
            />
          </Field>
        </div>
        <div className="border p-4">
          <h3 className="text-sm font-medium">Silence handling</h3>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <NumberField
              id="voice-reminder-trigger"
              label="Reminder after (ms)"
              min={1_000}
              max={300_000}
              value={form.values.reminderTriggerMs}
              onChange={(value) => change("reminderTriggerMs", value)}
            />
            <NumberField
              id="voice-reminder-count"
              label="Maximum reminders"
              min={0}
              max={10}
              value={form.values.reminderMaxCount}
              onChange={(value) => change("reminderMaxCount", value)}
            />
            <NumberField
              id="voice-silence-end"
              label="End after silence (ms)"
              min={0}
              max={3_600_000}
              value={form.values.endCallAfterSilenceMs}
              onChange={(value) => change("endCallAfterSilenceMs", value)}
            />
          </div>
          <div className="mt-4">
            <Field label="Reminder messages" htmlFor="voice-reminders">
              <Textarea
                id="voice-reminders"
                rows={3}
                value={form.values.reminderMessages}
                placeholder="One message per line"
                onChange={(event) =>
                  change("reminderMessages", event.target.value)
                }
              />
            </Field>
          </div>
        </div>
      </EditorGroup>
    );
  }

  if (section === "data") {
    return (
      <EditorGroup
        title="Recording and post-call data"
        description="Primary call processing continues; notification, upload, and redaction run without interrupting the call."
      >
        <div className="divide-y border">
          <SwitchRow
            checked={form.values.transcriptStorageEnabled}
            description="Persist the canonical transcript after post-call processing."
            id="voice-transcript-storage"
            label="Store transcript"
            onCheckedChange={(checked) =>
              change("transcriptStorageEnabled", checked)
            }
          />
          <SwitchRow
            checked={form.values.audioStorageEnabled}
            description="Upload the completed recording through the selected storage provider."
            id="voice-audio-storage"
            label="Store audio recording"
            onCheckedChange={(checked) =>
              change("audioStorageEnabled", checked)
            }
          />
          <SwitchRow
            checked={form.values.recordingConsentRequired}
            description="Attempt the recording notification before the greeting. Failure does not stop recording."
            id="voice-recording-notice"
            label="Send recording notification"
            onCheckedChange={(checked) =>
              change("recordingConsentRequired", checked)
            }
          />
          <SwitchRow
            checked={form.values.redactPiiInTranscripts}
            description="Run pattern-based transcript redaction after the call."
            id="voice-redact-transcript"
            label="Redact transcript PII"
            onCheckedChange={(checked) =>
              change("redactPiiInTranscripts", checked)
            }
          />
          <SwitchRow
            checked={form.values.redactPiiInLogs}
            description="Apply pattern-based redaction to voice log projections."
            id="voice-redact-logs"
            label="Redact log PII"
            onCheckedChange={(checked) => change("redactPiiInLogs", checked)}
          />
        </div>
        {form.values.audioStorageEnabled ? (
          <ProviderConfigReferenceField
            description="Receives completed recordings. Upload retries run independently of the call."
            field="storageProviderConfigId"
            label="Recording storage configuration"
            organizationId={organizationId}
            references={form.references}
            value={form.values.storageProviderConfigId}
            onChange={(value) => change("storageProviderConfigId", value)}
          />
        ) : null}
        <Field label="Recording notification" htmlFor="voice-recording-message">
          <Textarea
            id="voice-recording-message"
            rows={3}
            maxLength={1_000}
            disabled={!form.values.recordingConsentRequired}
            value={form.values.recordingConsentMessage}
            onChange={(event) =>
              change("recordingConsentMessage", event.target.value)
            }
          />
        </Field>
      </EditorGroup>
    );
  }

  return (
    <EditorGroup
      title="Observability"
      description="Control content-free metrics emitted by the voice pipeline."
    >
      <div className="divide-y border">
        <SwitchRow
          checked={form.values.metricsEnabled}
          description="Collect operational voice metrics for this config."
          id="voice-metrics"
          label="Voice metrics"
          onCheckedChange={(checked) => change("metricsEnabled", checked)}
        />
        <SwitchRow
          checked={form.values.vendorLatencyTrackingEnabled}
          description="Record provider latency without storing message content."
          id="voice-vendor-latency"
          label="Vendor latency tracking"
          onCheckedChange={(checked) =>
            change("vendorLatencyTrackingEnabled", checked)
          }
        />
      </div>
    </EditorGroup>
  );
}

function EditorGroup({
  children,
  description,
  title,
}: {
  children: React.ReactNode;
  description: string;
  title: string;
}) {
  return (
    <section className="space-y-5 border bg-card p-4 sm:p-5">
      <div>
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-1 max-w-2xl text-sm leading-5 text-muted-foreground">
          {description}
        </p>
      </div>
      {children}
    </section>
  );
}

function Field({
  children,
  hint,
  htmlFor,
  label,
  required = false,
}: {
  children: React.ReactNode;
  hint?: string;
  htmlFor: string;
  label: string;
  required?: boolean;
}) {
  return (
    <div className="grid min-w-0 gap-2">
      <Label htmlFor={htmlFor}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </Label>
      {children}
      {hint === undefined ? null : (
        <p className="text-xs leading-5 text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}

function NumberField({
  hint,
  id,
  label,
  max,
  min,
  onChange,
  step,
  value,
}: {
  hint?: string;
  id: string;
  label: string;
  max: number;
  min: number;
  onChange: (value: number) => void;
  step?: number;
  value: number;
}) {
  return (
    <Field hint={hint} label={label} htmlFor={id}>
      <Input
        id={id}
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </Field>
  );
}

function SwitchRow({
  checked,
  description,
  id,
  label,
  onCheckedChange,
}: {
  checked: boolean;
  description: string;
  id: string;
  label: string;
  onCheckedChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 p-4">
      <div>
        <Label htmlFor={id}>{label}</Label>
        <p className="mt-1 text-sm leading-5 text-muted-foreground">
          {description}
        </p>
      </div>
      <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} />
    </div>
  );
}

export { VoiceConfigEditorFields };
