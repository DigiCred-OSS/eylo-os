import { ArrowLeft, RotateCcw, Save } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
  type NavigateFunction,
} from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ProviderFieldControl } from "@/features/providers/ProviderFieldControl";
import {
  formatProviderDate,
  formatProviderFieldValue,
  formatProviderIdentifier,
} from "@/features/providers/provider-formatters";
import {
  providerCollectionPath,
  providerCreatePath,
  safeOrganizationReturnPath,
} from "@/features/providers/provider-navigation";
import {
  PROVIDER_CAPABILITIES,
  type ProviderCapability,
  type ProviderCapabilityDefinition,
  type ProviderConfigRecord,
  type ProviderDefinition,
  type ProviderFieldDefinition,
  type ProviderFieldValue,
  type ProviderFormMode,
  type ProviderFormSection,
  type ProviderFormValues,
} from "@/features/providers/providers.types";
import { cn } from "@/lib/utils";
import { useAsyncContextGuard } from "@/lib/use-async-context-guard";

const FORM_SECTIONS: readonly {
  description: string;
  id: ProviderFormSection;
  label: string;
}[] = [
  { description: "Choose the provider", id: "provider", label: "Provider" },
  { description: "Name this configuration", id: "identity", label: "Identity" },
  { description: "Provider behavior", id: "settings", label: "Settings" },
  {
    description: "Write-only credentials",
    id: "credentials",
    label: "Credentials",
  },
  { description: "Check before saving", id: "review", label: "Review" },
];

type SecretValues = Record<string, string | null>;

const ProviderConfigFormPage = observer(function ProviderConfigFormPage({
  mode,
}: {
  mode: ProviderFormMode;
}) {
  const { auth, providers } = useRootStore();
  const form = providers.form;
  const member = auth.member;
  const { capability: capabilityParam, configId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [secrets, setSecrets] = useState<SecretValues>({});
  const capability = parseCapability(capabilityParam);
  const definition =
    capability === null ? null : providers.definitionFor(capability);
  const section = parseSection(searchParams.get("section"), mode);
  const returnTo = safeOrganizationReturnPath(
    searchParams.get("returnTo"),
    organizationId,
  );
  const contextKey = `${organizationId ?? "missing"}:${mode}:${capabilityParam ?? "missing"}:${configId ?? "new"}`;
  const isCurrentContext = useAsyncContextGuard(contextKey);
  const visibleSections = useMemo(
    () =>
      mode === "create"
        ? FORM_SECTIONS
        : FORM_SECTIONS.filter((item) => item.id !== "provider"),
    [mode],
  );

  useEffect(() => {
    if (providers.catalog === null) {
      void providers.loadOverview();
    }
  }, [providers, providers.catalog]);

  useEffect(() => {
    if (
      capability === null ||
      definition === null ||
      member === null ||
      organizationId === undefined
    ) {
      return;
    }

    if (mode === "create") {
      form.beginCreate(
        {
          capability,
          memberKey: member.email,
          organizationId,
        },
        definition,
      );
    } else if (configId !== undefined) {
      void form.beginEdit(
        {
          capability,
          configId,
          memberKey: member.email,
          organizationId,
        },
        definition,
      );
    }
  }, [capability, configId, definition, form, member, mode, organizationId]);

  useEffect(() => {
    setSecrets({});
  }, [capability, configId, mode, organizationId]);

  if (organizationId === undefined || member === null) {
    return null;
  }
  if (capability === null) {
    return (
      <InvalidCapability
        organizationId={organizationId}
        onNavigate={navigate}
      />
    );
  }

  const isExpectedRoute =
    (mode === "create" && configId === undefined) ||
    (mode === "edit" && configId !== undefined);
  if (!isExpectedRoute) {
    return null;
  }

  const activeCapability: ProviderCapability = capability;
  const activeMember = member;
  const activeOrganizationId: string = organizationId;

  const contextMatches = form.matchesContext(
    {
      capability: activeCapability,
      configId: mode === "edit" ? (configId ?? null) : null,
      memberKey: activeMember.email,
      organizationId: activeOrganizationId,
    },
    mode,
  );
  const fields = contextMatches
    ? form.fields.filter((field) => form.fieldIsVisible(field))
    : [];
  const settingsFields = fields.filter((field) => !field.secret);
  const credentialFields = fields.filter((field) => field.secret);
  const providerDefinition = contextMatches ? form.providerDefinition : null;
  const hasSecretChanges = Object.keys(secrets).length > 0;

  function updateSection(nextSection: ProviderFormSection): void {
    const nextParams = new URLSearchParams(searchParams);
    if (nextSection === firstSection(mode)) {
      nextParams.delete("section");
    } else {
      nextParams.set("section", nextSection);
    }
    setSearchParams(nextParams);
  }

  function leaveForm(): void {
    if (returnTo !== null) {
      void navigate(returnTo);
      return;
    }
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("returnTo");
    nextParams.delete("section");
    const search = nextParams.toString();
    void navigate({
      pathname: providerCollectionPath(activeOrganizationId, activeCapability),
      search: search === "" ? "" : `?${search}`,
    });
  }

  function discardDraft(): void {
    setSecrets({});
    form.discardLocalDraft();
  }

  function selectProvider(providerId: string): void {
    setSecrets({});
    form.selectProvider(providerId);
  }

  function updateSecret(
    key: string,
    value: ProviderFieldValue | string | null | undefined,
  ): void {
    setSecrets((current) => {
      const next = { ...current };
      if (value === undefined || value === "") {
        delete next[key];
      } else if (typeof value === "string" || value === null) {
        next[key] = value;
      }
      return next;
    });
  }

  async function submit(): Promise<void> {
    const submittedContextKey = contextKey;
    const saved = await form.submit(secrets);
    if (!isCurrentContext(submittedContextKey)) {
      return;
    }
    if (saved === null) {
      const errorSection = firstErrorSection(form.fieldErrors, fields);
      if (errorSection !== null) {
        updateSection(errorSection);
      }
      return;
    }

    setSecrets({});
    leaveForm();
  }

  function retryEdit(): void {
    if (definition === null || configId === undefined) {
      return;
    }
    void form.beginEdit(
      {
        capability: activeCapability,
        configId,
        memberKey: activeMember.email,
        organizationId: activeOrganizationId,
      },
      definition,
    );
  }

  const title =
    mode === "create"
      ? `New ${definition?.label ?? formatProviderIdentifier(activeCapability)} configuration`
      : form.serverConfig?.name || "Edit provider configuration";
  const savedAt =
    form.savedAt === null ? null : formatProviderDate(form.savedAt).label;

  return (
    <section
      className="min-h-[calc(100svh-3.5rem)]"
      aria-labelledby="provider-form-title"
    >
      <header className="sticky top-14 z-10 flex min-h-16 flex-wrap items-center justify-between gap-3 border-b bg-background/95 px-4 py-3 backdrop-blur sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Leave provider configuration"
            title="Back"
            onClick={leaveForm}
          >
            <ArrowLeft aria-hidden="true" />
          </Button>
          <div className="min-w-0">
            <h1
              id="provider-form-title"
              className="truncate text-lg font-semibold tracking-tight"
            >
              {title}
            </h1>
            <p className="truncate text-xs text-muted-foreground">
              {form.hasLocalDraft && savedAt !== null
                ? `Non-secret draft saved locally ${savedAt}`
                : form.isDirty
                  ? "Saving non-secret draft locally…"
                  : "No unsaved non-secret changes"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {form.hasLocalDraft || hasSecretChanges ? (
            <Button
              variant="outline"
              type="button"
              disabled={form.isSubmitting}
              onClick={discardDraft}
            >
              <RotateCcw aria-hidden="true" />
              {mode === "create" ? "Start new" : "Discard changes"}
            </Button>
          ) : null}
          <Button
            type="submit"
            form="provider-config-form"
            disabled={
              !contextMatches ||
              definition === null ||
              providerDefinition === null ||
              form.isLoading ||
              form.isSubmitting ||
              (mode === "edit" && form.serverConfig === null)
            }
          >
            <Save aria-hidden="true" />
            {form.isSubmitting ? "Saving…" : "Save configuration"}
          </Button>
        </div>
      </header>

      <div className="grid lg:grid-cols-[15rem_minmax(0,48rem)] lg:justify-center lg:gap-10 lg:px-6">
        <nav
          className="flex gap-1 overflow-x-auto border-b p-3 lg:sticky lg:top-30 lg:block lg:h-fit lg:border-b-0 lg:p-6 lg:pr-0"
          aria-label="Provider configuration sections"
        >
          {visibleSections.map((item) => (
            <button
              key={item.id}
              className={cn(
                "min-w-fit rounded-md px-3 py-2 text-left text-sm transition-colors lg:block lg:w-full",
                section === item.id
                  ? "bg-muted font-medium text-foreground"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
              )}
              type="button"
              aria-current={section === item.id ? "step" : undefined}
              onClick={() => updateSection(item.id)}
            >
              <span className="block">{item.label}</span>
              <span className="mt-0.5 hidden text-xs font-normal text-muted-foreground lg:block">
                {item.description}
              </span>
            </button>
          ))}
        </nav>

        <div className="space-y-5 p-4 sm:p-6 lg:px-0 lg:py-8">
          <FormMessages
            draftStorageErrorMessage={form.draftStorageErrorMessage}
            errorMessage={form.errorMessage}
            overviewErrorMessage={providers.overviewErrorMessage}
            referenceErrorMessage={form.referenceErrorMessage}
          />

          {definition === null ? (
            <CatalogState
              errorMessage={providers.overviewErrorMessage}
              loading={providers.isOverviewLoading}
              onRetry={() => void providers.loadOverview()}
            />
          ) : !contextMatches || form.isLoading ? (
            <FormLoading />
          ) : mode === "edit" && form.serverConfig === null ? (
            <LoadFailure
              errorMessage={form.errorMessage}
              onBack={leaveForm}
              onRetry={retryEdit}
            />
          ) : (
            <form
              id="provider-config-form"
              onSubmit={(event) => {
                event.preventDefault();
                void submit();
              }}
            >
              <fieldset
                className="min-w-0 space-y-6 border-0 p-0"
                disabled={form.isSubmitting}
              >
                {section === "provider" && mode === "create" ? (
                  <ProviderSection
                    definition={definition}
                    selectedProvider={form.values.provider}
                    onSelect={selectProvider}
                  />
                ) : null}
                {section === "identity" ? (
                  <IdentitySection
                    error={form.fieldErrors.name}
                    mode={mode}
                    provider={providerDefinition}
                    value={form.values.name}
                    onChange={form.setName}
                  />
                ) : null}
                {section === "settings" ? (
                  <FieldsSection
                    fields={settingsFields}
                    formValues={form.values}
                    organizationId={activeOrganizationId}
                    referenceOptions={form.referenceOptions}
                    selectedProvider={providerDefinition}
                    errors={form.fieldErrors}
                    onChange={(field, value) =>
                      form.setConfigField(field.key, toConfigValue(value))
                    }
                  />
                ) : null}
                {section === "credentials" ? (
                  <CredentialsSection
                    fields={credentialFields}
                    formValues={form.values}
                    selectedProvider={providerDefinition}
                    secrets={secrets}
                    errors={form.fieldErrors}
                    hasStoredSecret={form.hasStoredSecret}
                    onChange={updateSecret}
                  />
                ) : null}
                {section === "review" ? (
                  <ReviewSection
                    credentialFields={credentialFields}
                    fields={settingsFields}
                    formValues={form.values}
                    provider={providerDefinition}
                    secrets={secrets}
                    hasStoredSecret={form.hasStoredSecret}
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

function ProviderSection({
  definition,
  onSelect,
  selectedProvider,
}: {
  definition: ProviderCapabilityDefinition;
  onSelect: (providerId: string) => void;
  selectedProvider: string;
}) {
  return (
    <FormSection
      description="Eylo has no preconfigured provider. Choose the service this configuration will use."
      title="Provider"
    >
      <div className="grid gap-3 sm:grid-cols-2" role="radiogroup">
        {definition.providers.map((provider) => {
          const selected = provider.id === selectedProvider;
          return (
            <button
              key={provider.id}
              className={cn(
                "min-h-28 border p-4 text-left transition-colors hover:bg-muted/60 focus-visible:outline-2 focus-visible:outline-offset-2",
                selected && "border-foreground bg-muted",
              )}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onSelect(provider.id)}
            >
              <span className="block text-sm font-medium">
                {provider.label}
              </span>
              <span className="mt-1 block text-xs text-muted-foreground">
                {formatProviderIdentifier(provider.id)}
              </span>
              {provider.description ? (
                <span className="mt-3 block text-sm leading-5 text-muted-foreground">
                  {provider.description}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </FormSection>
  );
}

function IdentitySection({
  error,
  mode,
  onChange,
  provider,
  value,
}: {
  error?: string;
  mode: ProviderFormMode;
  onChange: (name: string) => void;
  provider: ProviderDefinition | null;
  value: string;
}) {
  const descriptionId = "provider-config-name-description";
  const errorId = "provider-config-name-error";
  return (
    <FormSection
      description="Use a name teammates can recognize when assigning this configuration to an Agent."
      title="Identity"
    >
      {provider === null ? (
        <ChooseProviderNotice />
      ) : (
        <div className="space-y-5">
          {mode === "edit" ? (
            <ReadOnlyValue label="Provider" value={provider.label} />
          ) : null}
          <div className="space-y-2">
            <Label htmlFor="provider-config-name">
              Configuration name
              <span className="ml-1 text-destructive" aria-label="required">
                *
              </span>
            </Label>
            <Input
              id="provider-config-name"
              aria-describedby={`${descriptionId}${error ? ` ${errorId}` : ""}`}
              aria-invalid={error !== undefined}
              autoComplete="off"
              maxLength={255}
              placeholder={`Example: Production ${provider.label}`}
              value={value}
              onChange={(event) => onChange(event.target.value)}
            />
            <p id={descriptionId} className="text-xs text-muted-foreground">
              This name is visible to every member of the organization.
            </p>
            {error ? (
              <p id={errorId} className="text-xs text-destructive" role="alert">
                {error}
              </p>
            ) : null}
          </div>
        </div>
      )}
    </FormSection>
  );
}

function FieldsSection({
  errors,
  fields,
  formValues,
  onChange,
  organizationId,
  referenceOptions,
  selectedProvider,
}: {
  errors: Record<string, string>;
  fields: readonly ProviderFieldDefinition[];
  formValues: ProviderFormValues;
  onChange: (
    field: ProviderFieldDefinition,
    value: ProviderFieldValue | string | null | undefined,
  ) => void;
  organizationId: string;
  referenceOptions: Partial<Record<ProviderCapability, ProviderConfigRecord[]>>;
  selectedProvider: ProviderDefinition | null;
}) {
  const location = useLocation();
  if (selectedProvider === null) {
    return (
      <FormSection
        description="Configure how the selected provider behaves."
        title="Settings"
      >
        <ChooseProviderNotice />
      </FormSection>
    );
  }

  return (
    <FormSection
      description={`Settings accepted by ${selectedProvider.label}. Optional values are omitted so Eylo does not invent a platform default.`}
      title="Settings"
    >
      {fields.length === 0 ? (
        <p className="border p-4 text-sm text-muted-foreground">
          This provider has no additional non-secret settings.
        </p>
      ) : (
        <div className="space-y-5">
          {fields.map((field) => (
            <ProviderFieldControl
              key={field.key}
              configureReferencePath={
                field.reference_capability == null
                  ? undefined
                  : providerCreatePath(
                      organizationId,
                      field.reference_capability,
                      `${location.pathname}${location.search}`,
                    )
              }
              error={errors[field.key]}
              existingSecret={false}
              field={field}
              idPrefix="provider-setting"
              referenceOptions={
                field.reference_capability == null
                  ? []
                  : (referenceOptions[field.reference_capability] ?? [])
              }
              required={fieldIsRequired(field, formValues.config)}
              value={formValues.config[field.key]}
              onChange={(value) => onChange(field, value)}
            />
          ))}
        </div>
      )}
    </FormSection>
  );
}

function CredentialsSection({
  errors,
  fields,
  formValues,
  hasStoredSecret,
  onChange,
  secrets,
  selectedProvider,
}: {
  errors: Record<string, string>;
  fields: readonly ProviderFieldDefinition[];
  formValues: ProviderFormValues;
  hasStoredSecret: (field: ProviderFieldDefinition) => boolean;
  onChange: (
    key: string,
    value: ProviderFieldValue | string | null | undefined,
  ) => void;
  secrets: SecretValues;
  selectedProvider: ProviderDefinition | null;
}) {
  return (
    <FormSection
      description="Credentials are sent only when you save this configuration."
      title="Credentials"
    >
      <div className="border border-warning/40 bg-warning/10 p-4 text-sm leading-6">
        Credential values stay only in this open page. They are never saved in
        the browser draft or URL. Refreshing or leaving clears new values, so
        re-enter them before saving.
      </div>
      {selectedProvider === null ? (
        <ChooseProviderNotice />
      ) : fields.length === 0 ? (
        <p className="border p-4 text-sm text-muted-foreground">
          {selectedProvider.label} requires no credentials in this capability.
        </p>
      ) : (
        <div className="space-y-5">
          {fields.map((field) => (
            <ProviderFieldControl
              key={field.key}
              error={errors[field.key]}
              existingSecret={hasStoredSecret(field)}
              field={field}
              idPrefix="provider-credential"
              referenceOptions={[]}
              required={fieldIsRequired(field, formValues.config)}
              value={secrets[field.key]}
              onChange={(value) => onChange(field.key, value)}
            />
          ))}
        </div>
      )}
    </FormSection>
  );
}

function ReviewSection({
  credentialFields,
  fields,
  formValues,
  hasStoredSecret,
  provider,
  secrets,
}: {
  credentialFields: readonly ProviderFieldDefinition[];
  fields: readonly ProviderFieldDefinition[];
  formValues: ProviderFormValues;
  hasStoredSecret: (field: ProviderFieldDefinition) => boolean;
  provider: ProviderDefinition | null;
  secrets: SecretValues;
}) {
  return (
    <FormSection
      description="Saving creates an unverified revision. Verify it explicitly from the configuration list or detail drawer."
      title="Review"
    >
      {provider === null ? (
        <ChooseProviderNotice />
      ) : (
        <div className="space-y-6">
          <ReviewGroup title="Identity">
            <ReviewRow label="Name" value={formValues.name || "Not named"} />
            <ReviewRow label="Provider" value={provider.label} />
          </ReviewGroup>

          <ReviewGroup title="Settings">
            {fields.length === 0 ? (
              <ReviewRow label="Settings" value="No additional settings" />
            ) : (
              fields.map((field) => (
                <ReviewRow
                  key={field.key}
                  label={field.label}
                  value={formatProviderFieldValue(
                    formValues.config[field.key] ?? null,
                  )}
                />
              ))
            )}
          </ReviewGroup>

          <ReviewGroup title="Credentials">
            {credentialFields.length === 0 ? (
              <ReviewRow label="Credentials" value="No credentials required" />
            ) : (
              credentialFields.map((field) => (
                <ReviewRow
                  key={field.key}
                  label={field.label}
                  value={credentialState(
                    secrets[field.key],
                    hasStoredSecret(field),
                  )}
                />
              ))
            )}
          </ReviewGroup>

          <div className="border p-4 text-sm leading-6">
            Save does not contact the provider. After saving, run Verify to test
            the stored configuration. Eylo marks it ready only from server-owned
            lifecycle state.
          </div>
        </div>
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
    <section
      className="space-y-5 border p-5 sm:p-6"
      aria-labelledby={`section-${title}`}
    >
      <div>
        <h2
          id={`section-${title}`}
          className="text-base font-semibold tracking-tight"
        >
          {title}
        </h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          {description}
        </p>
      </div>
      {children}
    </section>
  );
}

function ReviewGroup({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <section className="space-y-3" aria-labelledby={`review-${title}`}>
      <h3
        id={`review-${title}`}
        className="text-sm font-semibold tracking-tight"
      >
        {title}
      </h3>
      <dl className="divide-y border px-4">{children}</dl>
    </section>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[12rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="break-words text-sm">{value}</dd>
    </div>
  );
}

function ReadOnlyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{label}</p>
      <div className="border bg-muted/30 px-3 py-2 text-sm">{value}</div>
      <p className="text-xs text-muted-foreground">
        Provider identity is immutable. Create another configuration to change
        it.
      </p>
    </div>
  );
}

function ChooseProviderNotice() {
  return (
    <p className="border p-4 text-sm text-muted-foreground">
      Choose a provider first. Eylo will not select one for you.
    </p>
  );
}

function FormMessages({
  draftStorageErrorMessage,
  errorMessage,
  overviewErrorMessage,
  referenceErrorMessage,
}: {
  draftStorageErrorMessage: string | null;
  errorMessage: string | null;
  overviewErrorMessage: string | null;
  referenceErrorMessage: string | null;
}) {
  const messages = [
    overviewErrorMessage,
    errorMessage,
    referenceErrorMessage,
    draftStorageErrorMessage,
  ].filter((message): message is string => message !== null);
  if (messages.length === 0) {
    return null;
  }
  return (
    <div className="space-y-2" role="alert">
      {[...new Set(messages)].map((message) => (
        <p key={message} className="border border-destructive/40 p-3 text-sm">
          {message}
        </p>
      ))}
    </div>
  );
}

function CatalogState({
  errorMessage,
  loading,
  onRetry,
}: {
  errorMessage: string | null;
  loading: boolean;
  onRetry: () => void;
}) {
  if (loading || errorMessage === null) {
    return <FormLoading />;
  }
  return (
    <div className="border p-8 text-center" role="alert">
      <p className="text-sm font-medium">
        Provider definitions are unavailable
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{errorMessage}</p>
      <Button
        className="mt-4"
        type="button"
        variant="outline"
        onClick={onRetry}
      >
        Try again
      </Button>
    </div>
  );
}

function FormLoading() {
  return (
    <div className="border p-8 text-center text-sm text-muted-foreground">
      Loading provider configuration…
    </div>
  );
}

function LoadFailure({
  errorMessage,
  onBack,
  onRetry,
}: {
  errorMessage: string | null;
  onBack: () => void;
  onRetry: () => void;
}) {
  return (
    <div className="border p-8 text-center" role="alert">
      <p className="text-sm font-medium">Configuration is unavailable</p>
      <p className="mt-1 text-sm text-muted-foreground">
        {errorMessage ?? "The configuration could not be loaded."}
      </p>
      <div className="mt-4 flex justify-center gap-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button type="button" onClick={onRetry}>
          Try again
        </Button>
      </div>
    </div>
  );
}

function InvalidCapability({
  onNavigate,
  organizationId,
}: {
  onNavigate: NavigateFunction;
  organizationId: string;
}) {
  return (
    <section className="p-6" role="alert">
      <p className="text-sm font-medium">Unknown provider capability</p>
      <Button
        className="mt-4"
        variant="outline"
        onClick={() => void onNavigate(`/org/${organizationId}/providers`)}
      >
        Back to Providers
      </Button>
    </section>
  );
}

function parseCapability(value: string | undefined): ProviderCapability | null {
  return PROVIDER_CAPABILITIES.find((item) => item === value) ?? null;
}

function parseSection(
  value: string | null,
  mode: ProviderFormMode,
): ProviderFormSection {
  const visible =
    mode === "create"
      ? FORM_SECTIONS
      : FORM_SECTIONS.filter((item) => item.id !== "provider");
  return visible.some((item) => item.id === value)
    ? (value as ProviderFormSection)
    : firstSection(mode);
}

function firstSection(mode: ProviderFormMode): ProviderFormSection {
  return mode === "create" ? "provider" : "identity";
}

function firstErrorSection(
  errors: Record<string, string>,
  fields: readonly ProviderFieldDefinition[],
): ProviderFormSection | null {
  if (errors.name !== undefined) {
    return "identity";
  }
  const errorKeys = new Set(Object.keys(errors));
  if (fields.some((field) => field.secret && errorKeys.has(field.key))) {
    return "credentials";
  }
  if (fields.some((field) => !field.secret && errorKeys.has(field.key))) {
    return "settings";
  }
  return null;
}

function fieldIsRequired(
  field: ProviderFieldDefinition,
  config: ProviderFormValues["config"],
): boolean {
  const condition = field.required_when;
  return (
    field.required ||
    (condition != null && config[condition.field] === condition.equals)
  );
}

function credentialState(
  value: string | null | undefined,
  stored: boolean,
): string {
  if (value === null) {
    return "Will be removed";
  }
  if (typeof value === "string" && value !== "") {
    return stored ? "Will be replaced" : "Will be stored";
  }
  return stored ? "Stored" : "Not configured";
}

function toConfigValue(
  value: ProviderFieldValue | string | null | undefined,
): ProviderFieldValue {
  return value === undefined ? null : value;
}

export { ProviderConfigFormPage };
