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
import { Textarea } from "@/components/ui/textarea";
import { AgentAccessSection } from "@/features/agents/AgentAccessSection";
import { AgentInstructionField } from "@/features/agents/AgentInstructionField";
import { AgentLlmOverridesFields } from "@/features/agents/AgentLlmOverridesFields";
import { AgentReferenceField } from "@/features/agents/AgentReferenceField";
import { AgentLifecycleSection } from "@/features/agents/AgentLifecycleSection";
import { AgentRelationshipsSection } from "@/features/agents/AgentRelationshipsSection";
import { AgentVoiceSection } from "@/features/agents/AgentVoiceSection";
import {
  formatAgentDate,
  formatAgentEnum,
} from "@/features/agents/agent-formatters";
import {
  AGENT_KINDS,
  type AgentFormMode,
  type AgentFormSection,
  type AgentFormValues,
  type AgentKind,
} from "@/features/agents/agents.types";
import { cn } from "@/lib/utils";
import { useAsyncContextGuard } from "@/lib/use-async-context-guard";
import { safeOrganizationReturnPath } from "@/features/providers/provider-navigation";

const FORM_SECTIONS: readonly {
  description: string;
  id: AgentFormSection;
  label: string;
}[] = [
  {
    description: "Identity and Agent type",
    id: "basics",
    label: "Basics",
  },
  {
    description: "Instructions and execution",
    id: "runtime",
    label: "Runtime",
  },
  {
    description: "External capability references",
    id: "providers",
    label: "Providers",
  },
  {
    description: "Reusable Voice Config",
    id: "voice",
    label: "Voice",
  },
  {
    description: "Tools and background work",
    id: "relationships",
    label: "Relationships",
  },
  {
    description: "Publish, withdraw, revoke, delete",
    id: "lifecycle",
    label: "Lifecycle",
  },
];

const AgentFormPage = observer(function AgentFormPage({
  mode,
}: {
  mode: AgentFormMode;
}) {
  const { agents, auth } = useRootStore();
  const form = agents.form;
  const member = auth.member;
  const { agentId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const contextKey = `${organizationId ?? "missing"}:${mode}:${agentId ?? "new"}`;
  const isCurrentContext = useAsyncContextGuard(contextKey);
  const section = parseFormSection(searchParams.get("section"), mode);
  const visibleSections =
    mode === "create"
      ? FORM_SECTIONS.filter(
          (formSection) =>
            formSection.id !== "relationships" &&
            formSection.id !== "lifecycle",
        )
      : FORM_SECTIONS;

  useEffect(() => {
    if (member === null || organizationId === undefined) {
      return;
    }

    if (mode === "create") {
      form.beginCreate({
        memberKey: member.email,
        organizationId,
      });
      return;
    }

    if (agentId !== undefined) {
      void form.beginEdit({
        agentId,
        memberKey: member.email,
        organizationId,
      });
    }
  }, [agentId, form, member, mode, organizationId]);

  if (member === null || organizationId === undefined) {
    return null;
  }

  const isExpectedRoute =
    (mode === "create" && agentId === undefined) ||
    (mode === "edit" && agentId !== undefined);

  if (!isExpectedRoute) {
    return null;
  }

  const returnPath = safeOrganizationReturnPath(
    searchParams.get("returnTo"),
    organizationId,
  );
  const returnLabel = returnPath?.startsWith(`/org/${organizationId}/knowledge`)
    ? "Back to Knowledge"
    : "Back to Agents";

  function updateSection(nextSection: AgentFormSection): void {
    const nextParams = new URLSearchParams(searchParams);
    if (nextSection === "basics") {
      nextParams.delete("section");
    } else {
      nextParams.set("section", nextSection);
    }
    setSearchParams(nextParams);
  }

  function returnToCollection(): void {
    if (returnPath !== null) {
      void navigate(returnPath);
      return;
    }
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("section");
    nextParams.delete("returnTo");
    const search = nextParams.toString();
    void navigate({
      pathname: `/org/${organizationId}/agents`,
      search: search === "" ? "" : `?${search}`,
    });
  }

  function changeField<Key extends keyof AgentFormValues>(
    field: Key,
    value: AgentFormValues[Key],
  ): void {
    setSavedNotice(null);
    form.setField(field, value);
  }

  async function submit(): Promise<void> {
    const submittedContextKey = contextKey;
    const savedAgent = await form.submit();
    if (savedAgent === null || !isCurrentContext(submittedContextKey)) {
      return;
    }

    setSavedNotice("Agent saved to Eylo.");

    if (mode === "create") {
      void navigate(
        {
          pathname: `/org/${organizationId}/agents/${savedAgent.id}/edit`,
          search: location.search,
        },
        { replace: true },
      );
    }
  }

  return (
    <section
      className="min-h-[calc(100svh-3.5rem)]"
      aria-labelledby="agent-form-title"
    >
      <header className="sticky top-14 z-10 flex min-h-16 flex-wrap items-center justify-between gap-3 border-b bg-background/95 px-4 py-3 backdrop-blur sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            aria-label={returnLabel}
            title={returnLabel}
            onClick={returnToCollection}
          >
            <ArrowLeft aria-hidden="true" />
          </Button>
          <div className="min-w-0">
            <h1
              id="agent-form-title"
              className="truncate text-lg font-semibold tracking-tight"
            >
              {mode === "create"
                ? "New Agent"
                : form.serverAgent?.name || "Edit Agent"}
            </h1>
            <p className="truncate text-xs text-muted-foreground">
              {form.hasLocalDraft && form.savedAt !== null
                ? `Draft saved locally ${formatAgentDate(form.savedAt)}`
                : form.isDirty
                  ? "Saving local draft…"
                  : "No unsaved local changes"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {mode === "create" && form.hasLocalDraft ? (
            <Button
              variant="outline"
              disabled={form.isSubmitting}
              onClick={() => {
                setSavedNotice(null);
                form.discardLocalDraft();
              }}
            >
              <RotateCcw aria-hidden="true" />
              Start new
            </Button>
          ) : null}
          <Button
            type="submit"
            form="agent-form"
            disabled={
              form.isLoading ||
              form.isSubmitting ||
              form.conflictMessage !== null ||
              (form.mode === "edit" && form.serverAgent === null)
            }
          >
            <Save aria-hidden="true" />
            {form.isSubmitting ? "Saving…" : "Save Agent"}
          </Button>
        </div>
      </header>

      <div className="grid lg:grid-cols-[15rem_minmax(0,48rem)] lg:justify-center lg:gap-10 lg:px-6">
        <nav
          className="flex gap-1 overflow-x-auto border-b p-3 lg:sticky lg:top-30 lg:block lg:h-fit lg:border-b-0 lg:p-6 lg:pr-0"
          aria-label="Agent form sections"
        >
          {visibleSections.map((formSection) => (
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
            hasLocalDraft={form.hasLocalDraft}
            savedAt={form.savedAt}
            savedNotice={!form.isDirty ? savedNotice : null}
            onDiscard={form.discardLocalDraft}
            onKeepLocal={form.keepLocalChanges}
            onUseServer={form.useServerVersion}
          />

          {form.isLoading ? (
            <div className="border p-8 text-center text-sm text-muted-foreground">
              Loading Agent…
            </div>
          ) : form.errorMessage !== null &&
            form.serverAgent === null &&
            mode === "edit" ? (
            <div className="border p-8 text-center">
              <p className="text-sm text-destructive">{form.errorMessage}</p>
              <Button
                className="mt-4"
                variant="outline"
                onClick={returnToCollection}
              >
                {returnLabel}
              </Button>
            </div>
          ) : (
            <form
              id="agent-form"
              onSubmit={(event) => {
                event.preventDefault();
                void submit();
              }}
            >
              <fieldset
                className="min-w-0 space-y-6 border-0 p-0"
                disabled={form.isSubmitting}
              >
                {section === "basics" ? (
                  <BasicsSection
                    mode={mode}
                    values={form.values}
                    onChange={changeField}
                  />
                ) : null}
                {section === "runtime" ? (
                  <RuntimeSection
                    agentId={agentId ?? null}
                    implementation={form.serverAgent?.implementation ?? null}
                    memberKey={member.email}
                    organizationId={organizationId}
                    values={form.values}
                    onChange={changeField}
                  />
                ) : null}
                {section === "providers" ? (
                  <ProvidersSection
                    organizationId={organizationId}
                    values={form.values}
                    onChange={changeField}
                  />
                ) : null}
                {section === "voice" ? (
                  <AgentVoiceSection
                    organizationId={organizationId}
                    values={form.values}
                    onChange={(value) => changeField("voiceConfigId", value)}
                  />
                ) : null}
                {section === "relationships" && agentId !== undefined ? (
                  <div className="space-y-5">
                    <AgentRelationshipsSection
                      agentId={agentId}
                      organizationId={organizationId}
                    />
                    <AgentAccessSection
                      agentId={agentId}
                      organizationId={organizationId}
                    />
                  </div>
                ) : null}
                {section === "lifecycle" && agentId !== undefined ? (
                  <AgentLifecycleSection
                    agentId={agentId}
                    organizationId={organizationId}
                    onDeleted={returnToCollection}
                  />
                ) : null}
              </fieldset>
            </form>
          )}
        </div>
      </div>
    </section>
  );
});

function BasicsSection({
  mode,
  onChange,
  values,
}: {
  mode: AgentFormMode;
  onChange: <Key extends keyof AgentFormValues>(
    field: Key,
    value: AgentFormValues[Key],
  ) => void;
  values: AgentFormValues;
}) {
  return (
    <FormSection
      title="Basics"
      description="Name the Agent and choose the runtime family it belongs to."
    >
      <FormField label="Name" htmlFor="agent-name" required>
        <Input
          id="agent-name"
          required
          maxLength={100}
          autoComplete="off"
          value={values.name}
          onChange={(event) => onChange("name", event.target.value)}
        />
      </FormField>

      <FormField
        label="Description"
        htmlFor="agent-description"
        hint="Explain the Agent's job in language teammates can scan."
      >
        <Textarea
          id="agent-description"
          rows={5}
          value={values.description}
          onChange={(event) => onChange("description", event.target.value)}
        />
      </FormField>

      <FormField
        label="Kind"
        htmlFor="agent-kind"
        hint={
          mode === "edit"
            ? "Kind is fixed after creation by the current API contract."
            : "Conversational Agents interact live. Background Agents run work outside a live conversation."
        }
      >
        <Select
          value={values.kind}
          disabled={mode === "edit"}
          onValueChange={(value) => {
            const kind = value as AgentKind;
            onChange("kind", kind);
            if (kind === "BACKGROUND") {
              onChange("voiceConfigId", null);
            }
          }}
        >
          <SelectTrigger id="agent-kind" className="w-full">
            <SelectValue>{formatAgentEnum(values.kind)}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {AGENT_KINDS.map((kind) => (
              <SelectItem key={kind} value={kind}>
                {formatAgentEnum(kind)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </FormField>
    </FormSection>
  );
}

function RuntimeSection({
  agentId,
  implementation,
  memberKey,
  onChange,
  organizationId,
  values,
}: {
  agentId: string | null;
  implementation: string | null;
  memberKey: string;
  onChange: <Key extends keyof AgentFormValues>(
    field: Key,
    value: AgentFormValues[Key],
  ) => void;
  organizationId: string;
  values: AgentFormValues;
}) {
  return (
    <FormSection
      title="Runtime"
      description="Bind the published instructions that drive this Agent."
    >
      {implementation === null ? (
        <AgentInstructionField
          agentId={agentId}
          memberKey={memberKey}
          organizationId={organizationId}
          value={values.instructionTemplateId}
          onChange={(value) => onChange("instructionTemplateId", value)}
        />
      ) : (
        <div className="border p-4">
          <p className="text-sm font-medium">Platform implementation</p>
          <p className="mt-1 text-sm leading-5 text-muted-foreground">
            This seeded background Agent runs vetted Eylo code and cannot bind
            member-authored instructions.
          </p>
          <code className="mt-3 block w-fit rounded-sm bg-muted px-1.5 py-1 text-xs">
            {implementation}
          </code>
        </div>
      )}
    </FormSection>
  );
}

function ProvidersSection({
  onChange,
  organizationId,
  values,
}: {
  onChange: <Key extends keyof AgentFormValues>(
    field: Key,
    value: AgentFormValues[Key],
  ) => void;
  organizationId: string;
  values: AgentFormValues;
}) {
  return (
    <FormSection
      title="Providers"
      description="Reference explicit organization configuration. Unset fields remain unconfigured."
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-6 border p-4">
          <div className="min-w-0">
            <Label htmlFor="agent-file-uploads">Allow file uploads</Label>
            <p className="mt-1 text-sm leading-5 text-muted-foreground">
              End users may add files to their conversation. Eylo creates and
              grants a private conversation Knowledgebase when the first file is
              uploaded.
            </p>
          </div>
          <Switch
            id="agent-file-uploads"
            checked={values.allowFileUploads}
            onCheckedChange={(checked) => {
              onChange("allowFileUploads", checked);
              if (!checked) {
                onChange("fileUploadEmbeddingProviderConfigId", null);
              }
            }}
          />
        </div>
        {values.allowFileUploads ? (
          <AgentReferenceField
            field="fileUploadEmbeddingProviderConfigId"
            label="File upload embedding provider"
            description="Exact semantic vector configuration for conversation files. The ready revision is pinned when this Agent is published."
            organizationId={organizationId}
            value={values.fileUploadEmbeddingProviderConfigId}
            onChange={(value) =>
              onChange("fileUploadEmbeddingProviderConfigId", value)
            }
          />
        ) : null}
        <AgentReferenceField
          field="llmProviderConfigId"
          label="Language model provider"
          description="Model inference used by this Agent."
          organizationId={organizationId}
          value={values.llmProviderConfigId}
          onChange={(value) => onChange("llmProviderConfigId", value)}
        />
        <AgentLlmOverridesFields
          llmProviderConfigId={values.llmProviderConfigId}
          values={values.llmOverrides}
          onChange={(value) => onChange("llmOverrides", value)}
        />
        <AgentReferenceField
          field="emailProviderConfigId"
          label="Email provider"
          description="Outbound and inbound email capability."
          organizationId={organizationId}
          value={values.emailProviderConfigId}
          onChange={(value) => onChange("emailProviderConfigId", value)}
        />
        <AgentReferenceField
          field="webrtcProviderConfigId"
          label="WebRTC provider"
          description="Browser voice transport for conversational Agents."
          organizationId={organizationId}
          value={values.webrtcProviderConfigId}
          onChange={(value) => onChange("webrtcProviderConfigId", value)}
        />
        <AgentReferenceField
          field="rerankingProviderConfigId"
          label="Reranking provider"
          description="Optional result reranking capability."
          organizationId={organizationId}
          value={values.rerankingProviderConfigId}
          onChange={(value) => onChange("rerankingProviderConfigId", value)}
        />
        <AgentReferenceField
          field="memoryProviderConfigId"
          label="Memory provider"
          description="Optional durable memory capability."
          organizationId={organizationId}
          value={values.memoryProviderConfigId}
          onChange={(value) => onChange("memoryProviderConfigId", value)}
        />
      </div>
    </FormSection>
  );
}

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
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>
        {label}
        {required ? <span aria-hidden="true"> *</span> : null}
      </Label>
      {children}
      {hint !== undefined ? (
        <p className="text-xs leading-5 text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

function FormMessages({
  conflictMessage,
  draftStorageErrorMessage,
  errorMessage,
  hasLocalDraft,
  onDiscard,
  onKeepLocal,
  onUseServer,
  savedAt,
  savedNotice,
}: {
  conflictMessage: string | null;
  draftStorageErrorMessage: string | null;
  errorMessage: string | null;
  hasLocalDraft: boolean;
  onDiscard: () => void;
  onKeepLocal: () => void;
  onUseServer: () => void;
  savedAt: string | null;
  savedNotice: string | null;
}) {
  return (
    <div className="space-y-3">
      {conflictMessage !== null ? (
        <div className="border border-warning/40 bg-warning/5 p-4" role="alert">
          <p className="text-sm font-medium text-warning">Version conflict</p>
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
      ) : null}

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

      {savedNotice !== null ? (
        <div
          className="flex items-center gap-2 border border-success/30 bg-success/5 p-3 text-sm text-success"
          role="status"
        >
          <Check className="size-4" aria-hidden="true" />
          {savedNotice}
        </div>
      ) : null}

      {hasLocalDraft && savedAt !== null && conflictMessage === null ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border bg-muted/40 p-3">
          <p className="text-sm text-muted-foreground">
            Local draft · {formatAgentDate(savedAt)}
          </p>
          <Button type="button" variant="ghost" size="sm" onClick={onDiscard}>
            Discard draft
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function parseFormSection(
  value: string | null,
  mode: AgentFormMode,
): AgentFormSection {
  return FORM_SECTIONS.some(
    (section) =>
      section.id === value &&
      (mode === "edit" ||
        (section.id !== "relationships" && section.id !== "lifecycle")),
  )
    ? (value as AgentFormSection)
    : "basics";
}

export { AgentFormPage };
