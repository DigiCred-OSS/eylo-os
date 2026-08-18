import { ArrowLeft, RotateCcw } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";

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
import { Skeleton } from "@/components/ui/skeleton";
import {
  PhoneNumberDraftStorage,
  type PhoneNumberDraft,
} from "@/features/telephony/phone-number-draft-storage";

type PhoneNumberFormMode = "create" | "edit";

const EMPTY_DRAFT: PhoneNumberDraft = {
  configId: "",
  inboundAgentId: "",
  label: "",
  number: "",
  outboundAgentId: "",
  status: "",
};

const PhoneNumberFormPage = observer(function PhoneNumberFormPage({
  mode,
}: {
  mode: PhoneNumberFormMode;
}) {
  const { auth, telephony } = useRootStore();
  const { organizationId, phoneNumberId } = useParams();
  const navigate = useNavigate();
  const storage = useMemo(
    () => new PhoneNumberDraftStorage(window.localStorage),
    [],
  );
  const [values, setValues] = useState<PhoneNumberDraft>(EMPTY_DRAFT);
  const [fieldErrors, setFieldErrors] = useState<
    Partial<Record<keyof PhoneNumberDraft, string>>
  >({});
  const [readyKey, setReadyKey] = useState<string | null>(null);
  const skipDraftWrite = useRef(true);

  const memberKey = auth.member?.email ?? "unknown-member";
  const storageScope =
    organizationId === undefined ? "" : `${organizationId}:${memberKey}`;
  const recordId = mode === "edit" ? (phoneNumberId ?? null) : null;
  const contextKey = `${storageScope}:${mode}:${recordId ?? "new"}`;
  const numbers = telephony.numbers;

  useEffect(() => {
    if (
      organizationId === undefined ||
      (mode === "edit" && phoneNumberId === undefined)
    )
      return;
    let active = true;
    skipDraftWrite.current = true;
    setReadyKey(null);
    setFieldErrors({});
    async function begin(): Promise<void> {
      const tasks: Promise<void>[] = [
        telephony.loadReferences(organizationId!),
      ];
      if (mode === "edit" && phoneNumberId !== undefined)
        tasks.push(numbers.loadSelected(phoneNumberId));
      await Promise.all(tasks);
      if (!active) return;
      const draft = storage.read(storageScope, recordId);
      const server = mode === "edit" ? numbers.selectedNumber : null;
      setValues(draft ?? (server === null ? EMPTY_DRAFT : fromServer(server)));
      setReadyKey(contextKey);
    }
    void begin();
    return () => {
      active = false;
    };
  }, [
    contextKey,
    mode,
    numbers,
    organizationId,
    phoneNumberId,
    recordId,
    storage,
    storageScope,
    telephony,
  ]);

  useEffect(() => {
    if (readyKey !== contextKey) return;
    if (skipDraftWrite.current) {
      skipDraftWrite.current = false;
      return;
    }
    storage.write(storageScope, recordId, values);
  }, [contextKey, readyKey, recordId, storage, storageScope, values]);

  if (organizationId === undefined) return null;
  const collectionPath = `/org/${organizationId}/telephony/numbers`;
  const isReady = readyKey === contextKey;
  const editUnavailable =
    mode === "edit" && isReady && numbers.selectedNumber === null;

  function setField<Field extends keyof PhoneNumberDraft>(
    field: Field,
    value: PhoneNumberDraft[Field],
  ): void {
    setValues((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
  }

  function reset(): void {
    storage.clear(storageScope, recordId);
    skipDraftWrite.current = true;
    setFieldErrors({});
    setValues(
      mode === "edit" && numbers.selectedNumber !== null
        ? fromServer(numbers.selectedNumber)
        : EMPTY_DRAFT,
    );
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    const errors = validate(values, mode);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    if (mode === "create") {
      const config = telephony.configs.find(
        (item) => item.id === values.configId && item.ready,
      );
      if (config === undefined) {
        setFieldErrors({ configId: "Select a ready telephony configuration." });
        return;
      }
      const saved = await numbers.register({
        inboundAgentId: optional(values.inboundAgentId),
        label: optional(values.label),
        number: values.number.trim(),
        outboundAgentId: optional(values.outboundAgentId),
        provider: config.provider,
        providerConfigId: config.id,
        providerConfigRevision: config.revision,
      });
      if (saved !== null) {
        storage.clear(storageScope, recordId);
        void navigate(`${collectionPath}/${saved.id}`, { replace: true });
      }
      return;
    }

    if (phoneNumberId === undefined) return;
    const saved = await numbers.update(phoneNumberId, {
      inboundAgentId: optional(values.inboundAgentId),
      label: optional(values.label),
      outboundAgentId: optional(values.outboundAgentId),
      status: values.status === "" ? null : values.status,
    });
    if (saved !== null) {
      storage.clear(storageScope, recordId);
      void navigate(`${collectionPath}/${saved.id}`, { replace: true });
    }
  }

  return (
    <section
      className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6"
      aria-labelledby="phone-number-form-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-3">
          <Button
            className="-ml-3"
            variant="ghost"
            onClick={() => void navigate(collectionPath)}
          >
            <ArrowLeft aria-hidden="true" />
            Phone numbers
          </Button>
          <div>
            <h1
              id="phone-number-form-title"
              className="text-2xl font-semibold tracking-tight"
            >
              {mode === "create"
                ? "Register phone number"
                : "Edit phone number"}
            </h1>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
              {mode === "create"
                ? "Register a number already owned in a configured carrier account. Use Find numbers to purchase a new carrier number."
                : "Manage platform availability and exact inbound or outbound Agent assignments."}
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          disabled={!isReady || editUnavailable}
          onClick={reset}
        >
          <RotateCcw aria-hidden="true" />
          {mode === "create" ? "Start new" : "Discard draft"}
        </Button>
      </header>

      {!isReady ||
      telephony.isReferencesLoading ||
      (mode === "edit" && numbers.isSelectedLoading) ? (
        <FormSkeleton />
      ) : editUnavailable ? (
        <div className="space-y-4 border border-destructive/30 bg-destructive/5 p-5">
          <p className="text-sm text-destructive" role="alert">
            {numbers.selectedErrorMessage ??
              "This phone number could not be loaded."}
          </p>
          <Button
            variant="outline"
            onClick={() => void navigate(collectionPath)}
          >
            <ArrowLeft aria-hidden="true" />
            Back to phone numbers
          </Button>
        </div>
      ) : (
        <form className="space-y-6" onSubmit={(event) => void submit(event)}>
          {telephony.referenceErrorMessage === null ? null : (
            <ErrorBox>{telephony.referenceErrorMessage}</ErrorBox>
          )}
          <FormSection
            title="Carrier authority"
            description="The exact ready carrier config and revision that owns this number."
          >
            {mode === "create" ? (
              <FormField
                id="phone-config"
                label="Telephony configuration"
                error={fieldErrors.configId}
              >
                <Select
                  value={values.configId || null}
                  onValueChange={(value) => setField("configId", value ?? "")}
                >
                  <SelectTrigger
                    id="phone-config"
                    className="w-full"
                    aria-invalid={fieldErrors.configId !== undefined}
                  >
                    <SelectValue placeholder="Select a ready configuration" />
                  </SelectTrigger>
                  <SelectContent>
                    {telephony.configs
                      .filter((config) => config.ready)
                      .map((config) => (
                        <SelectItem key={config.id} value={config.id}>
                          {config.name} · {config.provider} · revision{" "}
                          {config.revision}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
                {telephony.configs.some((config) => config.ready) ? null : (
                  <p className="text-xs leading-5 text-muted-foreground">
                    No ready telephony configuration.{" "}
                    <Link
                      className="underline underline-offset-4"
                      to={`/org/${organizationId}/providers/telephony`}
                    >
                      Configure a carrier first
                    </Link>
                    .
                  </p>
                )}
              </FormField>
            ) : (
              <ReadOnlyValue label="Configuration">
                {telephony.configName(numbers.selectedNumber!.providerConfigId)}{" "}
                · revision {numbers.selectedNumber!.providerConfigRevision}
              </ReadOnlyValue>
            )}
            <FormField
              id="phone-number"
              label="Phone number"
              description="E.164 format, including the leading + and country code."
              error={fieldErrors.number}
            >
              <Input
                id="phone-number"
                autoComplete="tel"
                disabled={mode === "edit"}
                inputMode="tel"
                maxLength={16}
                placeholder="+14155550123"
                value={values.number}
                aria-invalid={fieldErrors.number !== undefined}
                onChange={(event) => setField("number", event.target.value)}
              />
            </FormField>
            <FormField
              id="phone-label"
              label="Label"
              description="A human-readable purpose, such as Support or Sales."
              error={fieldErrors.label}
            >
              <Input
                id="phone-label"
                maxLength={255}
                value={values.label}
                onChange={(event) => setField("label", event.target.value)}
              />
            </FormField>
          </FormSection>

          <FormSection
            title="Agent routing"
            description="Agent mappings are optional. Calls without a matching assignment are not silently routed to a default Agent."
          >
            <AgentSelect
              id="phone-inbound-agent"
              label="Inbound Agent"
              agents={telephony.agents}
              value={values.inboundAgentId}
              onChange={(value) => setField("inboundAgentId", value)}
            />
            <AgentSelect
              id="phone-outbound-agent"
              label="Outbound Agent"
              agents={telephony.agents}
              value={values.outboundAgentId}
              onChange={(value) => setField("outboundAgentId", value)}
            />
          </FormSection>

          {mode === "edit" ? (
            <FormSection
              title="Availability"
              description="Only operator-controlled active or inactive states can be selected. Provisioning states belong to the platform."
            >
              <FormField
                id="phone-status"
                label="Status"
                error={fieldErrors.status}
              >
                <Select
                  value={values.status || "unchanged"}
                  onValueChange={(value) =>
                    setField(
                      "status",
                      value === "ACTIVE" || value === "INACTIVE" ? value : "",
                    )
                  }
                >
                  <SelectTrigger id="phone-status" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="unchanged">
                      Keep current platform state
                    </SelectItem>
                    <SelectItem value="ACTIVE">Active</SelectItem>
                    <SelectItem value="INACTIVE">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </FormField>
            </FormSection>
          ) : null}

          {numbers.actionErrorMessage === null ? null : (
            <ErrorBox>{numbers.actionErrorMessage}</ErrorBox>
          )}
          <div className="sticky bottom-0 flex flex-wrap justify-end gap-2 border bg-background/95 p-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
            <Button
              type="button"
              variant="outline"
              disabled={numbers.isActing}
              onClick={() => void navigate(collectionPath)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={numbers.isActing}>
              {numbers.isActing
                ? "Saving…"
                : mode === "create"
                  ? "Register number"
                  : "Save number"}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
});

function AgentSelect({
  agents,
  id,
  label,
  onChange,
  value,
}: {
  agents: readonly { id: string; name: string }[];
  id: string;
  label: string;
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <FormField
      id={id}
      label={label}
      description="Leave unassigned when this direction must not resolve to an Agent through this number."
    >
      <Select
        value={value || "unassigned"}
        onValueChange={(next) =>
          onChange(next === "unassigned" || next === null ? "" : next)
        }
      >
        <SelectTrigger id={id} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="unassigned">Not assigned</SelectItem>
          {agents.map((agent) => (
            <SelectItem key={agent.id} value={agent.id}>
              {agent.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </FormField>
  );
}

function FormSection({
  children,
  description,
  title,
}: {
  children: ReactNode;
  description: string;
  title: string;
}) {
  return (
    <section className="grid gap-5 border p-4 sm:p-5 lg:grid-cols-[14rem_minmax(0,1fr)]">
      <div>
        <h2 className="text-base font-medium">{title}</h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          {description}
        </p>
      </div>
      <div className="min-w-0 space-y-5">{children}</div>
    </section>
  );
}

function FormField({
  children,
  description,
  error,
  id,
  label,
}: {
  children: ReactNode;
  description?: string;
  error?: string;
  id: string;
  label: string;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {description === undefined ? null : (
        <p className="text-xs leading-5 text-muted-foreground">{description}</p>
      )}
      {children}
      {error === undefined ? null : (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

function ReadOnlyValue({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="space-y-1">
      <p className="text-sm font-medium">{label}</p>
      <p className="break-words text-sm text-muted-foreground">{children}</p>
    </div>
  );
}

function ErrorBox({ children }: { children: ReactNode }) {
  return (
    <div
      className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
      role="alert"
    >
      {children}
    </div>
  );
}

function FormSkeleton() {
  return (
    <div className="space-y-6">
      {Array.from({ length: 2 }, (_, index) => (
        <div className="border p-5" key={index}>
          <Skeleton className="h-5 w-36" />
          <Skeleton className="mt-6 h-9 w-full" />
          <Skeleton className="mt-5 h-9 w-full" />
        </div>
      ))}
    </div>
  );
}

function validate(
  values: PhoneNumberDraft,
  mode: PhoneNumberFormMode,
): Partial<Record<keyof PhoneNumberDraft, string>> {
  const errors: Partial<Record<keyof PhoneNumberDraft, string>> = {};
  if (mode === "create" && values.configId === "")
    errors.configId = "Select a telephony configuration.";
  if (mode === "create" && !/^\+[1-9]\d{1,14}$/.test(values.number.trim()))
    errors.number = "Enter a valid E.164 phone number.";
  if (values.label.length > 255)
    errors.label = "Label must be 255 characters or fewer.";
  return errors;
}

function optional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function fromServer(number: {
  inboundAgentId?: string | null;
  label?: string | null;
  number: string;
  outboundAgentId?: string | null;
  providerConfigId: string;
  status: string;
}): PhoneNumberDraft {
  return {
    configId: number.providerConfigId,
    inboundAgentId: number.inboundAgentId ?? "",
    label: number.label ?? "",
    number: number.number,
    outboundAgentId: number.outboundAgentId ?? "",
    status:
      number.status === "ACTIVE" || number.status === "INACTIVE"
        ? number.status
        : "",
  };
}

export { PhoneNumberFormPage };
