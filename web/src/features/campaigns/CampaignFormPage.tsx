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
import { Textarea } from "@/components/ui/textarea";
import { CampaignDraftStorage } from "@/features/campaigns/campaign-draft-storage";
import {
  campaignToForm,
  EMPTY_CAMPAIGN_FORM,
  toCampaignCreate,
  toCampaignUpdate,
  validateCampaignForm,
} from "@/features/campaigns/campaign-form";
import type {
  CampaignChannel,
  CampaignFormValues,
} from "@/features/campaigns/campaigns.types";

type CampaignFormMode = "create" | "edit";

const CampaignFormPage = observer(function CampaignFormPage({
  mode,
}: {
  mode: CampaignFormMode;
}) {
  const { auth, campaigns } = useRootStore();
  const { campaignId, organizationId } = useParams();
  const navigate = useNavigate();
  const storage = useMemo(
    () => new CampaignDraftStorage(window.localStorage),
    [],
  );
  const [values, setValues] = useState<CampaignFormValues>(EMPTY_CAMPAIGN_FORM);
  const [errors, setErrors] = useState<
    Partial<Record<keyof CampaignFormValues, string>>
  >({});
  const [readyKey, setReadyKey] = useState<string | null>(null);
  const skipDraftWrite = useRef(true);
  const memberKey = auth.member?.email ?? "unknown-member";
  const storageScope =
    organizationId === undefined ? "" : `${organizationId}:${memberKey}`;
  const recordId = mode === "edit" ? (campaignId ?? null) : null;
  const contextKey = `${storageScope}:${mode}:${recordId ?? "new"}`;

  useEffect(() => {
    if (
      organizationId === undefined ||
      (mode === "edit" && campaignId === undefined)
    )
      return;
    let active = true;
    skipDraftWrite.current = true;
    setReadyKey(null);
    setErrors({});
    async function begin(): Promise<void> {
      const work: Promise<void>[] = [campaigns.loadReferences(organizationId!)];
      if (mode === "edit" && campaignId !== undefined)
        work.push(campaigns.loadDefinition(organizationId!, campaignId));
      await Promise.all(work);
      if (!active) return;
      const local = storage.read(storageScope, recordId);
      const server = mode === "edit" ? campaigns.selectedCampaign : null;
      setValues(
        local ??
          (server === null ? EMPTY_CAMPAIGN_FORM : campaignToForm(server)),
      );
      setReadyKey(contextKey);
    }
    void begin();
    return () => {
      active = false;
    };
  }, [
    campaignId,
    campaigns,
    contextKey,
    mode,
    organizationId,
    recordId,
    storage,
    storageScope,
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
  const activeOrganizationId = organizationId;
  const collectionPath = `/org/${activeOrganizationId}/outbound/campaigns`;
  const isReady = readyKey === contextKey;
  const selected = campaigns.selectedCampaign;
  const editUnavailable =
    mode === "edit" &&
    isReady &&
    (selected === null || !["draft", "paused"].includes(selected.status));
  const readyEmailConfigIds = new Set(
    campaigns.emailConfigs.map((config) => config.id),
  );

  function setField<Field extends keyof CampaignFormValues>(
    field: Field,
    value: CampaignFormValues[Field],
  ): void {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
  }

  function reset(): void {
    storage.clear(storageScope, recordId);
    skipDraftWrite.current = true;
    setErrors({});
    setValues(
      mode === "edit" && selected !== null
        ? campaignToForm(selected)
        : EMPTY_CAMPAIGN_FORM,
    );
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    const validation = validateCampaignForm(values, readyEmailConfigIds);
    setErrors(validation);
    if (Object.keys(validation).length > 0) return;
    const saved =
      mode === "create"
        ? await campaigns.create(activeOrganizationId, toCampaignCreate(values))
        : campaignId === undefined || selected === null
          ? null
          : await campaigns.update(
              activeOrganizationId,
              campaignId,
              toCampaignUpdate(values, selected.publishedRevision),
            );
    if (saved !== null) {
      storage.clear(storageScope, recordId);
      void navigate(`${collectionPath}/${saved.id}`, { replace: true });
    }
  }

  return (
    <section
      className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6"
      aria-labelledby="campaign-form-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-3">
          <Button
            className="-ml-3"
            variant="ghost"
            onClick={() => void navigate(collectionPath)}
          >
            <ArrowLeft aria-hidden="true" />
            Campaigns
          </Button>
          <div>
            <h1
              id="campaign-form-title"
              className="text-2xl font-semibold tracking-tight"
            >
              {mode === "create" ? "New campaign" : "Edit campaign"}
            </h1>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
              Define one explicit channel, published Agent, delivery
              configuration, retry policy, and concurrency boundary. Recipients
              are added after creation.
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
      campaigns.isReferencesLoading ||
      (mode === "edit" && campaigns.isSelectedLoading) ? (
        <FormSkeleton />
      ) : editUnavailable ? (
        <div className="space-y-4 border border-destructive/30 bg-destructive/5 p-5">
          <p className="text-sm text-destructive" role="alert">
            {campaigns.selectedErrorMessage ??
              (selected === null
                ? "This campaign could not be loaded."
                : `Campaigns in ${selected.status} status cannot be edited.`)}
          </p>
          <Button
            variant="outline"
            onClick={() => void navigate(collectionPath)}
          >
            <ArrowLeft aria-hidden="true" />
            Back to campaigns
          </Button>
        </div>
      ) : (
        <form className="space-y-6" onSubmit={(event) => void submit(event)}>
          {campaigns.referenceErrorMessage === null ? null : (
            <ErrorBox>{campaigns.referenceErrorMessage}</ErrorBox>
          )}
          <FormSection
            title="Identity"
            description="How members recognize this outreach effort."
          >
            <Field id="campaign-name" label="Name" error={errors.name}>
              <Input
                id="campaign-name"
                maxLength={256}
                value={values.name}
                aria-invalid={errors.name !== undefined}
                onChange={(event) => setField("name", event.target.value)}
              />
            </Field>
            <Field id="campaign-description" label="Description" optional>
              <Textarea
                id="campaign-description"
                className="min-h-24"
                value={values.description}
                onChange={(event) =>
                  setField("description", event.target.value)
                }
              />
            </Field>
          </FormSection>
          <FormSection
            title="Channel and Agent"
            description="The Agent revision and channel configuration are pinned into every published campaign revision."
          >
            <Field
              id="campaign-channel"
              label="Outreach channel"
              error={errors.channel}
            >
              <Select
                value={values.channel || null}
                onValueChange={(value) => setField("channel", channel(value))}
              >
                <SelectTrigger
                  id="campaign-channel"
                  className="w-full"
                  aria-invalid={errors.channel !== undefined}
                >
                  <SelectValue placeholder="Select channel" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="voice">Voice</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="widget">Widget</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field
              id="campaign-agent"
              label="Published Agent"
              error={errors.agentId}
              description="Draft Agents are intentionally unavailable."
            >
              <Select
                value={values.agentId || null}
                onValueChange={(value) => setField("agentId", value ?? "")}
              >
                <SelectTrigger
                  id="campaign-agent"
                  className="w-full"
                  aria-invalid={errors.agentId !== undefined}
                >
                  <SelectValue placeholder="Select Agent" />
                </SelectTrigger>
                <SelectContent>
                  {campaigns.agents.map((agent) => (
                    <SelectItem value={agent.id} key={agent.id}>
                      {agent.name} · revision {agent.publishedRevision}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            {values.channel === "voice" ? (
              <p className="border-l-2 pl-3 text-sm leading-6 text-muted-foreground">
                Voice outreach resolves the phone number assigned to this Agent
                for outbound calls. No carrier is selected implicitly here.
              </p>
            ) : null}
            {values.channel === "email" ? (
              <EmailFields
                values={values}
                errors={errors}
                setField={setField}
                organizationId={activeOrganizationId}
              />
            ) : null}
            {values.channel === "widget" ? (
              <p className="border-l-2 pl-3 text-sm leading-6 text-muted-foreground">
                Widget outreach creates a conversation for each recipient. A
                published initial message template is required.
              </p>
            ) : null}
          </FormSection>
          {values.channel === "email" ? null : (
            <FormSection
              title="Initial message"
              description="Optional for voice; required for widget. The template revision is pinned when the campaign is saved."
            >
              <Field
                id="campaign-template"
                label="Published campaign template"
                error={errors.initialMessageTemplateId}
                optional={values.channel !== "widget"}
              >
                <Select
                  value={values.initialMessageTemplateId || "none"}
                  onValueChange={(value) =>
                    setField(
                      "initialMessageTemplateId",
                      value === "none" || value === null ? "" : value,
                    )
                  }
                >
                  <SelectTrigger id="campaign-template" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">
                      No initial message template
                    </SelectItem>
                    {campaigns.templates.map((template) => (
                      <SelectItem value={template.id} key={template.id}>
                        {template.name} · revision {template.published_revision}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </FormSection>
          )}
          <FormSection
            title="Execution boundaries"
            description="Concurrency and retry policy are explicit. The platform records every selected recipient and does not conditionally suppress outreach in V1."
          >
            <Field
              id="campaign-concurrency"
              label="Concurrent recipients"
              error={errors.concurrencyLimit}
              description="Whole number from 1 to 50."
            >
              <Input
                id="campaign-concurrency"
                inputMode="numeric"
                min={1}
                max={50}
                type="number"
                value={values.concurrencyLimit}
                onChange={(event) =>
                  setField("concurrencyLimit", event.target.value)
                }
              />
            </Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field
                id="campaign-max-retries"
                label="Maximum retries"
                error={errors.retryMaxRetries}
              >
                <Input
                  id="campaign-max-retries"
                  inputMode="numeric"
                  min={0}
                  type="number"
                  value={values.retryMaxRetries}
                  onChange={(event) =>
                    setField("retryMaxRetries", event.target.value)
                  }
                />
              </Field>
              <Field
                id="campaign-retry-backoff"
                label="Backoff seconds"
                error={errors.retryBackoffSeconds}
              >
                <Input
                  id="campaign-retry-backoff"
                  inputMode="numeric"
                  min={0}
                  type="number"
                  value={values.retryBackoffSeconds}
                  onChange={(event) =>
                    setField("retryBackoffSeconds", event.target.value)
                  }
                />
              </Field>
            </div>
            <Field
              id="campaign-retry-on"
              label="Retry outcome codes"
              optional
              description="Comma-separated channel outcome codes. Empty means no outcomes are retried."
            >
              <Input
                id="campaign-retry-on"
                value={values.retryOn}
                placeholder={retryPlaceholder(values.channel)}
                onChange={(event) => setField("retryOn", event.target.value)}
              />
            </Field>
          </FormSection>
          {campaigns.actionErrorMessage === null ? null : (
            <ErrorBox>{campaigns.actionErrorMessage}</ErrorBox>
          )}
          <div className="sticky bottom-0 flex flex-wrap justify-end gap-2 border bg-background/95 p-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
            <Button
              type="button"
              variant="outline"
              disabled={campaigns.isActing}
              onClick={() => void navigate(collectionPath)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={campaigns.isActing}>
              {campaigns.isActing
                ? "Saving…"
                : mode === "create"
                  ? "Create campaign"
                  : "Save revision"}
            </Button>
          </div>
        </form>
      )}
    </section>
  );
});

function EmailFields({
  errors,
  organizationId,
  setField,
  values,
}: {
  errors: Partial<Record<keyof CampaignFormValues, string>>;
  organizationId: string;
  setField: <FieldName extends keyof CampaignFormValues>(
    field: FieldName,
    value: CampaignFormValues[FieldName],
  ) => void;
  values: CampaignFormValues;
}) {
  const { campaigns } = useRootStore();
  return (
    <>
      <Field
        id="campaign-email-config"
        label="Ready email configuration"
        error={errors.emailConfigId}
      >
        <Select
          value={values.emailConfigId || null}
          onValueChange={(value) => setField("emailConfigId", value ?? "")}
        >
          <SelectTrigger id="campaign-email-config" className="w-full">
            <SelectValue placeholder="Select configuration" />
          </SelectTrigger>
          <SelectContent>
            {campaigns.emailConfigs.map((config) => (
              <SelectItem value={config.id} key={config.id}>
                {config.name} · {config.provider} · revision {config.revision}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {campaigns.emailConfigs.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No ready email configuration.{" "}
            <Link
              className="underline underline-offset-4"
              to={`/org/${organizationId}/providers/email`}
            >
              Configure email first
            </Link>
            .
          </p>
        ) : null}
      </Field>
      <Field
        id="campaign-email-subject"
        label="Subject template"
        error={errors.emailSubjectTemplate}
        description="Use simple placeholders such as {{name}}."
      >
        <Input
          id="campaign-email-subject"
          value={values.emailSubjectTemplate}
          onChange={(event) =>
            setField("emailSubjectTemplate", event.target.value)
          }
        />
      </Field>
      <Field
        id="campaign-email-body"
        label="HTML body template"
        error={errors.emailBodyTemplate}
        description="Rendered against each recipient's campaign variables."
      >
        <Textarea
          id="campaign-email-body"
          className="min-h-40 font-mono text-xs"
          value={values.emailBodyTemplate}
          onChange={(event) =>
            setField("emailBodyTemplate", event.target.value)
          }
        />
      </Field>
    </>
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
function Field({
  children,
  description,
  error,
  id,
  label,
  optional = false,
}: {
  children: ReactNode;
  description?: string;
  error?: string;
  id: string;
  label: string;
  optional?: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <Label htmlFor={id}>{label}</Label>
        {optional ? (
          <span className="text-xs text-muted-foreground">Optional</span>
        ) : null}
      </div>
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
      {Array.from({ length: 3 }, (_, index) => (
        <div className="border p-5" key={index}>
          <Skeleton className="h-5 w-36" />
          <Skeleton className="mt-6 h-9 w-full" />
          <Skeleton className="mt-5 h-9 w-full" />
        </div>
      ))}
    </div>
  );
}
function channel(value: string | null): CampaignChannel | "" {
  return value === "voice" || value === "email" || value === "widget"
    ? value
    : "";
}
function retryPlaceholder(value: CampaignChannel | ""): string {
  if (value === "voice") return "customer_busy, customer_did_not_answer";
  if (value === "email") return "bounced, deferred";
  return "No retry outcomes";
}

export { CampaignFormPage };
