import { ArrowLeft, RotateCcw, Save } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  AutomationDraftStorage,
  automationDraftKey,
} from "@/features/automations/automation-draft-storage";
import {
  createDefaultScheduleValues,
  scheduleToFormValues,
  toCreateInput,
  toUpdateInput,
  validateScheduleValues,
} from "@/features/automations/automation-form";
import type { ScheduleFormValues } from "@/features/automations/automations.types";
import { formatProviderIdentifier } from "@/features/providers/provider-formatters";

interface AutomationFormPageProps {
  mode: "create" | "edit";
}

const TIMEZONES = supportedTimezones();

const AutomationFormPage = observer(function AutomationFormPage({
  mode,
}: AutomationFormPageProps) {
  const { auth, automations } = useRootStore();
  const { organizationId, scheduleId } = useParams();
  const navigate = useNavigate();
  const draftStorage = useMemo(
    () => new AutomationDraftStorage(window.localStorage),
    [],
  );
  const [values, setValues] = useState<ScheduleFormValues>(
    createDefaultScheduleValues,
  );
  const [localError, setLocalError] = useState<string | null>(null);
  const [draftRestored, setDraftRestored] = useState(false);
  const initializedContext = useRef<string | null>(null);
  const skipNextDraftWrite = useRef(false);
  const member = auth.member;
  const context =
    organizationId === undefined || member === null
      ? null
      : automationDraftKey(organizationId, member.id, mode, scheduleId);

  useEffect(() => {
    if (organizationId !== undefined)
      void automations.loadReferences(organizationId);
  }, [automations, organizationId]);
  useEffect(() => {
    if (
      mode === "edit" &&
      organizationId !== undefined &&
      scheduleId !== undefined
    ) {
      void automations.loadSelected(organizationId, scheduleId);
    }
  }, [automations, mode, organizationId, scheduleId]);
  useEffect(() => {
    if (context === null || initializedContext.current === context) return;
    if (mode === "edit" && automations.selectedSchedule === null) return;
    const draft = draftStorage.load(context);
    setValues(
      draft?.values ??
        (mode === "edit" && automations.selectedSchedule !== null
          ? scheduleToFormValues(automations.selectedSchedule)
          : createDefaultScheduleValues()),
    );
    setDraftRestored(draft !== null);
    initializedContext.current = context;
    skipNextDraftWrite.current = true;
  }, [automations.selectedSchedule, context, draftStorage, mode]);
  useEffect(() => {
    if (context !== null && initializedContext.current === context) {
      if (skipNextDraftWrite.current) {
        skipNextDraftWrite.current = false;
        return;
      }
      draftStorage.save(context, values);
    }
  }, [context, draftStorage, values]);

  if (organizationId === undefined || member === null) return null;
  const activeOrganizationId = organizationId;
  const schedule = automations.selectedSchedule;
  const isEditReady = mode === "create" || schedule !== null;

  function update<Key extends keyof ScheduleFormValues>(
    key: Key,
    value: ScheduleFormValues[Key],
  ): void {
    setValues((current) => ({ ...current, [key]: value }));
    setLocalError(null);
  }

  function leave(): void {
    void navigate(
      `/org/${activeOrganizationId}/automations${scheduleId === undefined ? "" : `/${scheduleId}`}`,
    );
  }

  function discardDraft(): void {
    if (context === null) return;
    draftStorage.clear(context);
    setValues(
      mode === "edit" && schedule !== null
        ? scheduleToFormValues(schedule)
        : createDefaultScheduleValues(),
    );
    setDraftRestored(false);
    setLocalError(null);
  }

  async function submit(
    event: React.FormEvent<HTMLFormElement>,
  ): Promise<void> {
    event.preventDefault();
    const validation = validateScheduleValues(values);
    if (validation !== null) {
      setLocalError(validation);
      return;
    }
    const saved =
      mode === "create"
        ? await automations.create(activeOrganizationId, toCreateInput(values))
        : scheduleId !== undefined && schedule !== null
          ? await automations.update(
              activeOrganizationId,
              scheduleId,
              toUpdateInput(values, schedule.published_revision),
            )
          : null;
    if (saved === null) return;
    if (context !== null) draftStorage.clear(context);
    initializedContext.current = null;
    void navigate(`/org/${activeOrganizationId}/automations/${saved.id}`, {
      replace: true,
    });
  }

  return (
    <section
      className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6"
      aria-labelledby="automation-form-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Back to Automations"
            title="Back to Automations"
            onClick={leave}
          >
            <ArrowLeft aria-hidden="true" />
          </Button>
          <div className="space-y-1">
            <h1
              id="automation-form-title"
              className="text-2xl font-semibold tracking-tight"
            >
              {mode === "create"
                ? "New automation"
                : `Edit ${schedule?.name ?? "automation"}`}
            </h1>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              Every trigger pins a published Agent revision. The Agent decides
              whether tools or a sandbox are needed when the run starts.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            Draft saved locally
          </span>
          <Button variant="outline" size="sm" onClick={discardDraft}>
            <RotateCcw aria-hidden="true" />
            {draftRestored ? "Discard restored draft" : "Start anew"}
          </Button>
        </div>
      </header>

      {mode === "edit" && automations.selectedErrorMessage !== null ? (
        <div
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          role="alert"
        >
          {automations.selectedErrorMessage}
        </div>
      ) : null}

      {!isEditReady ? (
        <div className="border p-8 text-sm text-muted-foreground">
          Loading automation…
        </div>
      ) : (
        <form className="space-y-8" onSubmit={(event) => void submit(event)}>
          <FormSection
            title="Purpose"
            description="Name the trigger, choose its Agent, and select a server-registered action."
          >
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Name" htmlFor="automation-name">
                <Input
                  id="automation-name"
                  maxLength={256}
                  value={values.name}
                  onChange={(event) => update("name", event.target.value)}
                />
              </Field>
              <Field
                label="Stable key"
                htmlFor="automation-key"
                help="Immutable after creation. Use lowercase letters, numbers, dots, underscores, or hyphens."
              >
                <Input
                  id="automation-key"
                  maxLength={128}
                  disabled={mode === "edit"}
                  value={values.key}
                  onChange={(event) =>
                    update(
                      "key",
                      event.target.value
                        .toLocaleLowerCase()
                        .replaceAll(" ", "-"),
                    )
                  }
                />
              </Field>
              <Field
                label="Published Agent"
                htmlFor="automation-agent"
                help="Only Agents with a published revision can be scheduled."
              >
                <Select
                  value={values.agentId || null}
                  disabled={automations.isReferencesLoading}
                  onValueChange={(value) => update("agentId", value ?? "")}
                >
                  <SelectTrigger id="automation-agent" className="w-full">
                    <SelectValue>
                      {automations.agents.find(
                        (agent) => agent.id === values.agentId,
                      )?.name ?? "Choose an Agent"}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {automations.agents.map((agent) => (
                      <SelectItem key={agent.id} value={agent.id}>
                        {agent.name} · revision {agent.publishedRevision}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field
                label="Action"
                htmlFor="automation-action"
                help="Actions come from the running platform registry; free-form names are not accepted."
              >
                <Select
                  value={values.action || null}
                  disabled={automations.isReferencesLoading}
                  onValueChange={(value) => update("action", value ?? "")}
                >
                  <SelectTrigger id="automation-action" className="w-full">
                    <SelectValue>
                      {values.action === ""
                        ? "Choose an action"
                        : formatProviderIdentifier(values.action)}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {automations.actions.map((action) => (
                      <SelectItem key={action} value={action}>
                        {formatProviderIdentifier(action)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>
          </FormSection>

          <FormSection
            title="Timing"
            description="Anchor recurrence in an explicit IANA timezone so wall-clock time survives daylight saving changes."
          >
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Timezone" htmlFor="automation-timezone">
                <Select
                  value={values.timezone}
                  onValueChange={(value) => {
                    if (value !== null) update("timezone", value);
                  }}
                >
                  <SelectTrigger id="automation-timezone" className="w-full">
                    <SelectValue>{values.timezone}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {TIMEZONES.map((timezone) => (
                      <SelectItem key={timezone} value={timezone}>
                        {timezone.replaceAll("_", " ")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Starts at" htmlFor="automation-start">
                <Input
                  id="automation-start"
                  type="datetime-local"
                  value={values.startsAt}
                  onChange={(event) => update("startsAt", event.target.value)}
                />
              </Field>
              <Field label="Recurrence" htmlFor="automation-recurrence">
                <Select
                  value={values.recurrence}
                  onValueChange={(value) => {
                    if (value !== null)
                      update(
                        "recurrence",
                        value as ScheduleFormValues["recurrence"],
                      );
                  }}
                >
                  <SelectTrigger id="automation-recurrence" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="once">One time</SelectItem>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="weekdays">Weekdays</SelectItem>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="custom">Custom RRULE</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field
                label="Ends at"
                htmlFor="automation-end"
                help="Optional. Leave empty for an ongoing recurring schedule."
              >
                <Input
                  id="automation-end"
                  type="datetime-local"
                  value={values.endsAt}
                  onChange={(event) => update("endsAt", event.target.value)}
                />
              </Field>
              {values.recurrence === "custom" ? (
                <Field
                  label="RRULE"
                  htmlFor="automation-rule"
                  help="RFC 5545 rule without DTSTART, for example FREQ=MONTHLY;BYMONTHDAY=1."
                >
                  <Input
                    id="automation-rule"
                    value={values.rule}
                    onChange={(event) =>
                      update("rule", event.target.value.toLocaleUpperCase())
                    }
                  />
                </Field>
              ) : null}
              <Field label="If runs were missed" htmlFor="automation-misfire">
                <Select
                  value={values.misfirePolicy}
                  onValueChange={(value) => {
                    if (value !== null)
                      update(
                        "misfirePolicy",
                        value as ScheduleFormValues["misfirePolicy"],
                      );
                  }}
                >
                  <SelectTrigger id="automation-misfire" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="coalesce">
                      Run the latest occurrence once
                    </SelectItem>
                    <SelectItem value="fire_all">
                      Run every missed occurrence
                    </SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            </div>
          </FormSection>

          <FormSection
            title="Action input"
            description="This JSON object is visible to the Agent and the selected action. Keep secrets in provider configurations, not here."
          >
            <Field label="Payload" htmlFor="automation-payload">
              <Textarea
                id="automation-payload"
                className="min-h-48 font-mono text-xs"
                spellCheck={false}
                value={values.payload}
                onChange={(event) => update("payload", event.target.value)}
              />
            </Field>
          </FormSection>

          {localError !== null || automations.actionErrorMessage !== null ? (
            <div
              className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
              role="alert"
            >
              {localError ?? automations.actionErrorMessage}
            </div>
          ) : null}

          <div className="flex flex-wrap justify-end gap-2 border-t pt-5">
            <Button
              type="button"
              variant="outline"
              disabled={automations.isActing}
              onClick={leave}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={automations.isActing || automations.isReferencesLoading}
            >
              <Save aria-hidden="true" />
              {automations.isActing
                ? "Saving…"
                : mode === "create"
                  ? "Create automation"
                  : "Save new revision"}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
});

function FormSection({
  children,
  description,
  title,
}: {
  children: React.ReactNode;
  description: string;
  title: string;
}) {
  return (
    <section className="grid gap-5 border-t pt-6 md:grid-cols-[14rem_minmax(0,1fr)]">
      <div>
        <h2 className="font-medium">{title}</h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          {description}
        </p>
      </div>
      <div>{children}</div>
    </section>
  );
}

function Field({
  children,
  help,
  htmlFor,
  label,
}: {
  children: React.ReactNode;
  help?: string;
  htmlFor: string;
  label: string;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {help === undefined ? null : (
        <p className="text-xs leading-5 text-muted-foreground">{help}</p>
      )}
    </div>
  );
}

function supportedTimezones(): string[] {
  const browserIntl = Intl as typeof Intl & {
    supportedValuesOf?: (key: "timeZone") => string[];
  };
  const timezones = browserIntl.supportedValuesOf?.("timeZone") ?? ["UTC"];
  return timezones.includes("UTC") ? timezones : ["UTC", ...timezones];
}

export { AutomationFormPage };
