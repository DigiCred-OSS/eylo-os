import { ArrowLeft, Check, RotateCcw, Save } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useState, type ReactNode } from "react";
import {
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";

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
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { formatKnowledgeDate } from "@/features/knowledge/knowledge-formatters";
import type { KnowledgeFormStore } from "@/features/knowledge/knowledge-form.store";
import {
  KNOWLEDGE_CHUNKING_STRATEGIES,
  KNOWLEDGE_SCOPES,
  KNOWLEDGE_VENDORS,
  type KnowledgebaseFormMode,
  type KnowledgebaseFormValues,
  type KnowledgeChunkingStrategy,
  type KnowledgeScope,
  type KnowledgeVendor,
} from "@/features/knowledge/knowledge.types";
import {
  providerCollectionPath,
  withReturnContext,
} from "@/features/providers/provider-navigation";
import { cn } from "@/lib/utils";
import { useAsyncContextGuard } from "@/lib/use-async-context-guard";

type KnowledgeFormSection = "basics" | "retrieval" | "scope";

const FORM_SECTIONS: readonly {
  description: string;
  id: KnowledgeFormSection;
  label: string;
}[] = [
  { description: "Identity and writes", id: "basics", label: "Basics" },
  {
    description: "Search and chunking",
    id: "retrieval",
    label: "Retrieval",
  },
  { description: "Knowledge ownership", id: "scope", label: "Scope" },
];

const KnowledgebaseFormPage = observer(function KnowledgebaseFormPage({
  mode,
}: {
  mode: KnowledgebaseFormMode;
}) {
  const { auth, knowledge } = useRootStore();
  const form = knowledge.form;
  const member = auth.member;
  const { knowledgebaseId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const section = parseFormSection(searchParams.get("section"));
  const contextKey = `${organizationId ?? "missing"}:${mode}:${knowledgebaseId ?? "new"}`;
  const isCurrentContext = useAsyncContextGuard(contextKey);

  useEffect(() => {
    if (member === null || organizationId === undefined) {
      return;
    }
    if (mode === "create") {
      form.beginCreate({ memberKey: member.email, organizationId });
    } else if (knowledgebaseId !== undefined) {
      void form.beginEdit({
        knowledgebaseId,
        memberKey: member.email,
        organizationId,
      });
    }
  }, [form, knowledgebaseId, member, mode, organizationId]);

  if (member === null || organizationId === undefined) {
    return null;
  }
  const isExpectedRoute =
    (mode === "create" && knowledgebaseId === undefined) ||
    (mode === "edit" && knowledgebaseId !== undefined);
  if (!isExpectedRoute) {
    return null;
  }

  function updateSection(nextSection: KnowledgeFormSection): void {
    const nextParams = new URLSearchParams(searchParams);
    if (nextSection === "basics") {
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
      pathname: `/org/${organizationId}/knowledge`,
      search: search === "" ? "" : `?${search}`,
    });
  }

  async function submit(): Promise<void> {
    const submittedContextKey = contextKey;
    const saved = await form.submit();
    if (saved === null) {
      const errorSection = firstErrorSection(form.fieldErrors);
      if (errorSection !== null && errorSection !== section) {
        updateSection(errorSection);
      }
      return;
    }
    if (!isCurrentContext(submittedContextKey)) {
      return;
    }
    knowledge.upsertKnowledgebase(saved);
    setSavedNotice("Knowledgebase saved to Eylo.");
    if (mode === "create") {
      void navigate(
        {
          pathname: `/org/${organizationId}/knowledge/${saved.id}/edit`,
          search: location.search,
        },
        { replace: true },
      );
    }
  }

  return (
    <section
      className="min-h-[calc(100svh-3.5rem)]"
      aria-labelledby="knowledge-form-title"
    >
      <header className="sticky top-14 z-10 flex min-h-16 flex-wrap items-center justify-between gap-3 border-b bg-background/95 px-4 py-3 backdrop-blur sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Back to Knowledge"
            title="Back to Knowledge"
            onClick={returnToCollection}
          >
            <ArrowLeft aria-hidden="true" />
          </Button>
          <div className="min-w-0">
            <h1
              id="knowledge-form-title"
              className="truncate text-lg font-semibold tracking-tight"
            >
              {mode === "create"
                ? "New knowledgebase"
                : form.serverKnowledgebase?.name || "Edit knowledgebase"}
            </h1>
            <p className="truncate text-xs text-muted-foreground">
              {form.hasLocalDraft && form.savedAt !== null
                ? `Draft saved locally ${formatKnowledgeDate(form.savedAt).label}`
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
            form="knowledgebase-form"
            disabled={
              form.isLoading ||
              form.isSubmitting ||
              (mode === "edit" && form.serverKnowledgebase === null)
            }
          >
            <Save aria-hidden="true" />
            {form.isSubmitting ? "Saving…" : "Save knowledgebase"}
          </Button>
        </div>
      </header>

      <div className="grid lg:grid-cols-[15rem_minmax(0,48rem)] lg:justify-center lg:gap-10 lg:px-6">
        <nav
          className="flex gap-1 overflow-x-auto border-b p-3 lg:sticky lg:top-30 lg:block lg:h-fit lg:border-b-0 lg:p-6 lg:pr-0"
          aria-label="Knowledgebase form sections"
        >
          {FORM_SECTIONS.map((formSection) => {
            const hasError = sectionHasErrors(form.fieldErrors, formSection.id);
            return (
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
                <span className="flex items-center gap-2">
                  {formSection.label}
                  {hasError ? (
                    <span className="text-xs font-normal text-destructive">
                      Review
                    </span>
                  ) : null}
                </span>
                <span className="mt-0.5 hidden text-xs font-normal text-muted-foreground lg:block">
                  {formSection.description}
                </span>
              </button>
            );
          })}
        </nav>

        <div className="space-y-5 p-4 sm:p-6 lg:px-0 lg:py-8">
          <FormMessages
            draftStorageErrorMessage={form.draftStorageErrorMessage}
            errorMessage={form.errorMessage}
            hasLocalDraft={form.hasLocalDraft}
            referenceErrorMessage={form.referenceErrorMessage}
            savedAt={form.savedAt}
            savedNotice={!form.isDirty ? savedNotice : null}
            onDiscard={form.discardLocalDraft}
            onRetryReferences={() => void form.reloadReferences()}
          />

          {form.isLoading ? (
            <div className="border p-8 text-center text-sm text-muted-foreground">
              Loading knowledgebase…
            </div>
          ) : form.errorMessage !== null &&
            form.serverKnowledgebase === null &&
            mode === "edit" ? (
            <div className="border p-8 text-center">
              <p className="text-sm text-destructive">{form.errorMessage}</p>
              <Button
                className="mt-4"
                variant="outline"
                onClick={returnToCollection}
              >
                Back to Knowledge
              </Button>
            </div>
          ) : (
            <form
              id="knowledgebase-form"
              onSubmit={(event) => {
                event.preventDefault();
                void submit();
              }}
            >
              <fieldset
                className="min-w-0 space-y-6 border-0 p-0"
                disabled={form.isSubmitting}
              >
                {section === "basics" ? <BasicsSection form={form} /> : null}
                {section === "retrieval" ? (
                  <RetrievalSection
                    form={form}
                    mode={mode}
                    organizationId={organizationId}
                    returnTo={`${location.pathname}${location.search}`}
                  />
                ) : null}
                {section === "scope" ? (
                  <ScopeSection form={form} mode={mode} />
                ) : null}
              </fieldset>
            </form>
          )}
        </div>
      </div>
    </section>
  );
});

function BasicsSection({ form }: { form: KnowledgeFormStore }) {
  return (
    <FormSection
      title="Basics"
      description="Name this retrieval boundary and decide whether explicit Agent grants may write into it."
    >
      <FormField
        error={form.fieldErrors.name}
        htmlFor="knowledgebase-name"
        label="Name"
        required
      >
        <Input
          id="knowledgebase-name"
          required
          maxLength={128}
          autoComplete="off"
          aria-invalid={form.fieldErrors.name !== undefined}
          value={form.values.name}
          onChange={(event) => form.setField("name", event.target.value)}
        />
      </FormField>

      <div className="flex items-center justify-between gap-6 border p-4">
        <div>
          <Label htmlFor="knowledgebase-writable">Accept Agent writes</Label>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            This only permits a future read-write grant. Every Agent still needs
            an explicit grant; imported content remains available for reads.
          </p>
        </div>
        <Switch
          id="knowledgebase-writable"
          checked={form.values.writable}
          onCheckedChange={(checked) => form.setField("writable", checked)}
        />
      </div>
    </FormSection>
  );
}

function RetrievalSection({
  form,
  mode,
  organizationId,
  returnTo,
}: {
  form: KnowledgeFormStore;
  mode: KnowledgebaseFormMode;
  organizationId: string;
  returnTo: string;
}) {
  const embeddingPath = withReturnContext(
    providerCollectionPath(organizationId, "embedding"),
    returnTo,
  );
  const selectedEmbedding = form.embeddingConfigs.find(
    (config) => config.id === form.values.embeddingProviderConfigId,
  );

  return (
    <FormSection
      title="Retrieval"
      description="Choose how matches are found, then make chunk boundaries explicit."
    >
      {mode === "create" ? (
        <FormField
          error={form.fieldErrors.vendor}
          htmlFor="knowledgebase-vendor"
          label="Search method"
          hint="Keyword search needs no external model. Semantic search pins one ready embedding configuration. Eylo chooses neither for you."
          required
        >
          <Select
            value={form.values.vendor || null}
            onValueChange={(value) => form.setVendor(value as KnowledgeVendor)}
          >
            <SelectTrigger
              id="knowledgebase-vendor"
              className="w-full"
              aria-invalid={form.fieldErrors.vendor !== undefined}
            >
              <SelectValue>
                {form.values.vendor === ""
                  ? "Choose a search method"
                  : formatVendor(form.values.vendor)}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {KNOWLEDGE_VENDORS.map((vendor) => (
                <SelectItem key={vendor} value={vendor}>
                  {formatVendor(vendor)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FormField>
      ) : (
        <ImmutableField label="Search method">
          {form.serverKnowledgebase === null
            ? "Unavailable"
            : formatVendor(form.serverKnowledgebase.vendor)}
        </ImmutableField>
      )}

      {mode === "create" && form.values.vendor === "pgvector" ? (
        <FormField
          error={form.fieldErrors.embeddingProviderConfigId}
          htmlFor="knowledgebase-embedding"
          label="Embedding provider configuration"
          hint="The current ready revision, model, and dimensions are pinned when this knowledgebase is created."
          required
        >
          <Select
            value={form.values.embeddingProviderConfigId}
            disabled={form.isReferencesLoading}
            onValueChange={(value) =>
              form.setField("embeddingProviderConfigId", value)
            }
          >
            <SelectTrigger
              id="knowledgebase-embedding"
              className="w-full"
              aria-invalid={
                form.fieldErrors.embeddingProviderConfigId !== undefined
              }
            >
              <SelectValue>
                {selectedEmbedding === undefined
                  ? form.isReferencesLoading
                    ? "Loading configurations…"
                    : "Choose a ready configuration"
                  : `${selectedEmbedding.name} · ${selectedEmbedding.provider} · revision ${selectedEmbedding.revision}`}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {form.readyEmbeddingConfigs.map((config) => (
                <SelectItem key={config.id} value={config.id}>
                  {config.name} · {config.provider} · revision {config.revision}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!form.isReferencesLoading &&
          form.readyEmbeddingConfigs.length === 0 ? (
            <p className="mt-2 text-xs text-muted-foreground">
              No ready embedding configuration. Configure and verify one in{" "}
              <a className="underline underline-offset-4" href={embeddingPath}>
                Providers
              </a>
              .
            </p>
          ) : null}
        </FormField>
      ) : null}

      {mode === "edit" && form.serverKnowledgebase?.vendor === "pgvector" ? (
        <div className="space-y-3 border p-4">
          <p className="text-sm font-medium">Pinned embedding authority</p>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <ReadOnlyValue
              label="Provider"
              value={
                form.serverKnowledgebase.embedding_provider ?? "Unavailable"
              }
            />
            <ReadOnlyValue
              label="Model"
              value={form.serverKnowledgebase.embedding_model ?? "Unavailable"}
            />
            <ReadOnlyValue
              label="Dimensions"
              value={String(
                form.serverKnowledgebase.embedding_dimensions ?? "Unavailable",
              )}
            />
            <ReadOnlyValue
              label="Revision"
              value={String(
                form.serverKnowledgebase.embedding_provider_config_revision ??
                  "Unavailable",
              )}
            />
          </dl>
          <p className="text-xs leading-5 text-muted-foreground">
            Retrieval space is immutable after creation so stored vectors cannot
            silently change meaning.
          </p>
        </div>
      ) : null}

      <Separator />

      <FormField
        htmlFor="knowledgebase-chunking"
        label="Chunking strategy"
        hint="Paragraph packs prose, Markdown preserves headed sections, and fixed cuts unstructured text."
      >
        <Select
          value={form.values.chunking}
          onValueChange={(value) =>
            form.setField("chunking", value as KnowledgeChunkingStrategy)
          }
        >
          <SelectTrigger id="knowledgebase-chunking" className="w-full">
            <SelectValue>{formatChunking(form.values.chunking)}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {KNOWLEDGE_CHUNKING_STRATEGIES.map((strategy) => (
              <SelectItem key={strategy} value={strategy}>
                {formatChunking(strategy)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </FormField>

      <div className="grid gap-5 sm:grid-cols-2">
        <FormField
          error={form.fieldErrors.chunkSize}
          htmlFor="knowledgebase-chunk-size"
          label="Chunk size"
          hint="Characters per retrieval unit. Allowed: 80–32,000."
        >
          <Input
            id="knowledgebase-chunk-size"
            type="number"
            inputMode="numeric"
            min={80}
            max={32_000}
            step={1}
            aria-invalid={form.fieldErrors.chunkSize !== undefined}
            value={form.values.chunkSize}
            onChange={(event) => form.setField("chunkSize", event.target.value)}
          />
        </FormField>
        <FormField
          error={form.fieldErrors.chunkOverlap}
          htmlFor="knowledgebase-chunk-overlap"
          label="Overlap"
          hint="Characters repeated across adjacent chunks. Must be smaller than chunk size."
        >
          <Input
            id="knowledgebase-chunk-overlap"
            type="number"
            inputMode="numeric"
            min={0}
            step={1}
            aria-invalid={form.fieldErrors.chunkOverlap !== undefined}
            value={form.values.chunkOverlap}
            onChange={(event) =>
              form.setField("chunkOverlap", event.target.value)
            }
          />
        </FormField>
      </div>
    </FormSection>
  );
}

function ScopeSection({
  form,
  mode,
}: {
  form: KnowledgeFormStore;
  mode: KnowledgebaseFormMode;
}) {
  const selectedAgent = form.agentOptions.find(
    (agent) => agent.id === form.values.scopeId,
  );
  return (
    <FormSection
      title="Scope"
      description="Scope decides which product object owns this knowledge. It is fixed after creation."
    >
      {mode === "edit" ? (
        <div className="space-y-4">
          <ImmutableField label="Scope">
            {formatScope(form.serverKnowledgebase?.scope ?? form.values.scope)}
          </ImmutableField>
          <ImmutableField label="Scope ID">
            <code className="break-all rounded-sm bg-muted px-1 py-0.5 text-xs">
              {form.serverKnowledgebase?.scope_id ?? form.values.scopeId}
            </code>
          </ImmutableField>
        </div>
      ) : (
        <>
          <FormField
            error={form.fieldErrors.scope}
            htmlFor="knowledgebase-scope"
            label="Owner scope"
            hint="Organization knowledge can be granted to Agents in this organization. Agent and conversation scopes narrow ownership further."
            required
          >
            <Select
              value={form.values.scope || null}
              onValueChange={(value) => form.setScope(value as KnowledgeScope)}
            >
              <SelectTrigger
                id="knowledgebase-scope"
                className="w-full"
                aria-invalid={form.fieldErrors.scope !== undefined}
              >
                <SelectValue>
                  {form.values.scope === ""
                    ? "Choose an owner scope"
                    : formatScope(form.values.scope)}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {KNOWLEDGE_SCOPES.map((scope) => (
                  <SelectItem key={scope} value={scope}>
                    {formatScope(scope)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

          {form.values.scope === "organization" ? (
            <div className="border bg-muted/30 p-4">
              <p className="text-sm font-medium">Current organization</p>
              <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                {form.values.scopeId}
              </p>
            </div>
          ) : null}

          {form.values.scope === "agent" ? (
            <FormField
              error={form.fieldErrors.scopeId}
              htmlFor="knowledgebase-agent-scope"
              label="Owning Agent"
              required
            >
              <Select
                value={form.values.scopeId || null}
                disabled={form.isReferencesLoading}
                onValueChange={(value) => {
                  if (value !== null) {
                    form.setField("scopeId", value);
                  }
                }}
              >
                <SelectTrigger
                  id="knowledgebase-agent-scope"
                  className="w-full"
                  aria-invalid={form.fieldErrors.scopeId !== undefined}
                >
                  <SelectValue>
                    {selectedAgent === undefined
                      ? form.isReferencesLoading
                        ? "Loading Agents…"
                        : "Choose an Agent"
                      : `${selectedAgent.label} · ${selectedAgent.lifecycle}`}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {form.agentOptions.map((agent) => (
                    <SelectItem key={agent.id} value={agent.id}>
                      {agent.label} · {agent.kind.toLowerCase()} ·{" "}
                      {agent.lifecycle}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {!form.isReferencesLoading && form.agentOptions.length === 0 ? (
                <p className="mt-2 text-xs text-muted-foreground">
                  No Agents exist in this organization yet.
                </p>
              ) : null}
            </FormField>
          ) : null}

          {form.values.scope === "conversation" ? (
            <FormField
              error={form.fieldErrors.scopeId}
              htmlFor="knowledgebase-conversation-scope"
              label="Conversation ID"
              hint="Paste the exact conversation UUID. The API verifies it belongs to this organization."
              required
            >
              <Input
                id="knowledgebase-conversation-scope"
                autoComplete="off"
                spellCheck={false}
                aria-invalid={form.fieldErrors.scopeId !== undefined}
                value={form.values.scopeId}
                onChange={(event) =>
                  form.setField("scopeId", event.target.value)
                }
              />
            </FormField>
          ) : null}
        </>
      )}
    </FormSection>
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
    <div className="border bg-card">
      <div className="space-y-1 p-5">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm leading-5 text-muted-foreground">{description}</p>
      </div>
      <Separator />
      <div className="space-y-6 p-5">{children}</div>
    </div>
  );
}

function FormField({
  children,
  error,
  hint,
  htmlFor,
  label,
  required = false,
}: {
  children: ReactNode;
  error?: string;
  hint?: string;
  htmlFor: string;
  label: string;
  required?: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </Label>
      {children}
      {error !== undefined ? (
        <p className="text-xs leading-5 text-destructive">{error}</p>
      ) : hint !== undefined ? (
        <p className="text-xs leading-5 text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

function ImmutableField({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="grid gap-2 border p-4 sm:grid-cols-[11rem_minmax(0,1fr)]">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="min-w-0 text-sm font-medium">{children}</span>
    </div>
  );
}

function ReadOnlyValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-all">{value}</dd>
    </div>
  );
}

function FormMessages({
  draftStorageErrorMessage,
  errorMessage,
  hasLocalDraft,
  onDiscard,
  onRetryReferences,
  referenceErrorMessage,
  savedAt,
  savedNotice,
}: {
  draftStorageErrorMessage: string | null;
  errorMessage: string | null;
  hasLocalDraft: boolean;
  onDiscard: () => void;
  onRetryReferences: () => void;
  referenceErrorMessage: string | null;
  savedAt: string | null;
  savedNotice: string | null;
}) {
  return (
    <div className="space-y-3">
      {draftStorageErrorMessage !== null ? (
        <div
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          role="alert"
        >
          {draftStorageErrorMessage}
        </div>
      ) : null}
      {errorMessage !== null ? (
        <div
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          role="alert"
        >
          {errorMessage}
        </div>
      ) : null}
      {referenceErrorMessage !== null ? (
        <div
          className="flex flex-wrap items-center justify-between gap-3 border p-3"
          role="alert"
        >
          <p className="text-sm text-muted-foreground">
            {referenceErrorMessage}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetryReferences}
          >
            Retry options
          </Button>
        </div>
      ) : null}
      {savedNotice !== null ? (
        <div
          className="flex items-center gap-2 border border-success/30 bg-success/5 p-3 text-sm text-success"
          role="status"
        >
          <Check className="size-4" aria-hidden="true" />
          {savedNotice}
        </div>
      ) : null}
      {hasLocalDraft && savedAt !== null ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border bg-muted/40 p-3">
          <p className="text-sm text-muted-foreground">
            Local draft · {formatKnowledgeDate(savedAt).label}
          </p>
          <Button type="button" variant="ghost" size="sm" onClick={onDiscard}>
            Discard draft
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function parseFormSection(value: string | null): KnowledgeFormSection {
  return FORM_SECTIONS.some((section) => section.id === value)
    ? (value as KnowledgeFormSection)
    : "basics";
}

const SECTION_FIELDS: Record<
  KnowledgeFormSection,
  readonly (keyof KnowledgebaseFormValues)[]
> = {
  basics: ["name", "writable"],
  retrieval: [
    "vendor",
    "embeddingProviderConfigId",
    "chunking",
    "chunkSize",
    "chunkOverlap",
  ],
  scope: ["scope", "scopeId"],
};

function firstErrorSection(
  errors: Partial<Record<keyof KnowledgebaseFormValues, string>>,
): KnowledgeFormSection | null {
  return (
    FORM_SECTIONS.find((section) => sectionHasErrors(errors, section.id))?.id ??
    null
  );
}

function sectionHasErrors(
  errors: Partial<Record<keyof KnowledgebaseFormValues, string>>,
  section: KnowledgeFormSection,
): boolean {
  return SECTION_FIELDS[section].some((field) => errors[field] !== undefined);
}

function formatVendor(vendor: KnowledgeVendor | string): string {
  return vendor === "postgres_fts"
    ? "Postgres keyword search"
    : vendor === "pgvector"
      ? "pgvector semantic search"
      : vendor;
}

function formatScope(scope: KnowledgeScope | ""): string {
  if (scope === "") {
    return "Unavailable";
  }
  return `${scope.charAt(0).toUpperCase()}${scope.slice(1)}`;
}

function formatChunking(strategy: KnowledgeChunkingStrategy): string {
  return `${strategy.charAt(0).toUpperCase()}${strategy.slice(1)}`;
}

export { KnowledgebaseFormPage };
