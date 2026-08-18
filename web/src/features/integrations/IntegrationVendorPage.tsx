import {
  ArrowLeft,
  ExternalLink,
  KeyRound,
  Link2,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
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
import { Skeleton } from "@/components/ui/skeleton";
import { ConnectionDeleteDialog } from "@/features/integrations/ConnectionDeleteDialog";
import { formatIntegrationDate } from "@/features/integrations/integration-formatters";
import {
  CONNECTION_KIND_LABELS,
  CONNECTION_STATUS_LABELS,
  INTEGRATION_AUTH_LABELS,
} from "@/features/integrations/integration-list-controls";
import { safeIntegrationReturnPath } from "@/features/integrations/integration-navigation";
import type {
  CuratedAuthKind,
  CuratedConnection,
  CuratedInstalledTool,
  CuratedVendorDetail,
} from "@/features/integrations/integrations.types";

const IntegrationVendorPage = observer(function IntegrationVendorPage() {
  const { auth, integrations } = useRootStore();
  const { organizationId, vendor } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [oauthSecret, setOauthSecret] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [connectionPendingDelete, setConnectionPendingDelete] =
    useState<CuratedConnection | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (organizationId && vendor) {
      void Promise.all([
        integrations.loadCatalog(organizationId),
        integrations.loadVendor(organizationId, vendor),
      ]);
    }
    return integrations.clearSelected;
  }, [integrations, organizationId, vendor]);

  useEffect(() => {
    if (
      organizationId &&
      vendor &&
      integrations.selectedVendor &&
      auth.member
    ) {
      integrations.prepareDraft(
        {
          memberKey: auth.member.email,
          organizationId,
          vendor,
        },
        integrations.selectedVendor,
      );
    }
  }, [
    auth.member,
    integrations,
    integrations.selectedVendor,
    organizationId,
    vendor,
  ]);

  if (!organizationId || !vendor) return null;
  const activeOrganizationId = organizationId;
  const activeVendor = vendor;
  const returnTo = safeIntegrationReturnPath(
    new URLSearchParams(location.search).get("returnTo"),
    activeOrganizationId,
  );

  function back(): void {
    if (returnTo !== null) {
      void navigate(returnTo);
      return;
    }
    void navigate({
      pathname: `/org/${activeOrganizationId}/integrations`,
      search: location.search,
    });
  }

  async function install(): Promise<void> {
    const saved = await integrations.install(activeOrganizationId, oauthSecret);
    if (saved) setOauthSecret("");
  }

  async function connectCredential(): Promise<void> {
    const detail = integrations.selectedVendor;
    if (!detail) return;
    const authKind = integrations.selectedInstallation?.authKind;
    const saved = await integrations.connect(
      activeOrganizationId,
      authKind === "api_key" ? { apiKey } : { username, password },
    );
    if (saved) {
      setApiKey("");
      setUsername("");
      setPassword("");
    }
  }

  async function authorize(): Promise<void> {
    const start = await integrations.beginAuthorization(activeOrganizationId);
    if (!start) return;
    try {
      await openAuthorizationPopup(
        start.authorizationUrl,
        start.callbackOrigin,
        activeVendor,
      );
      await integrations.refreshSelected(activeOrganizationId, activeVendor);
    } catch (error) {
      integrations.setActionError(
        error instanceof Error ? error.message : "Authorization failed.",
      );
    }
  }

  async function deleteConnection(): Promise<boolean> {
    if (!connectionPendingDelete) return false;
    const deleted = await integrations.deleteConnection(
      activeOrganizationId,
      connectionPendingDelete.id,
    );
    if (deleted) setConnectionPendingDelete(null);
    return deleted;
  }

  function requestConnectionDeletion(connection: CuratedConnection): void {
    integrations.clearActionError();
    setConnectionPendingDelete(connection);
  }

  return (
    <section
      className="min-w-0 space-y-6 p-4 sm:p-6"
      aria-labelledby="integration-title"
    >
      <header className="flex min-w-0 items-start gap-3">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Back to Integrations"
          title="Back to Integrations"
          onClick={back}
        >
          <ArrowLeft aria-hidden="true" />
        </Button>
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1
              id="integration-title"
              className="break-words text-2xl font-semibold tracking-tight"
            >
              {integrations.selectedVendor?.displayName ?? "Integration"}
            </h1>
            {integrations.selectedVendor?.installed ? (
              <Badge variant="secondary">Configured</Badge>
            ) : null}
          </div>
          <p className="max-w-3xl break-words text-sm leading-6 text-muted-foreground">
            {integrations.selectedVendor?.description ??
              "Loading curated vendor details…"}
          </p>
        </div>
      </header>

      {integrations.actionErrorMessage ? (
        <div
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          role="alert"
        >
          {integrations.actionErrorMessage}
        </div>
      ) : null}
      {integrations.selectedErrorMessage ? (
        <LoadFailure
          message={integrations.selectedErrorMessage}
          onRetry={() =>
            void integrations.loadVendor(activeOrganizationId, vendor)
          }
        />
      ) : null}

      {integrations.isSelectedLoading && !integrations.selectedVendor ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : integrations.selectedVendor ? (
        integrations.selectedVendor.installed ? (
          <InstalledVendor
            apiKey={apiKey}
            password={password}
            username={username}
            vendor={integrations.selectedVendor}
            connections={integrations.selectedConnections}
            tools={integrations.selectedTools}
            isActing={integrations.isActing}
            onApiKeyChange={setApiKey}
            onAuthorize={() => void authorize()}
            onConnect={() => void connectCredential()}
            onDeleteConnection={requestConnectionDeletion}
            onPasswordChange={setPassword}
            onToolModeChange={(tool, mode) =>
              void integrations.setExecutionMode(
                activeOrganizationId,
                tool,
                mode,
              )
            }
            onUsernameChange={setUsername}
          />
        ) : (
          <InstallVendorForm
            oauthSecret={oauthSecret}
            vendor={integrations.selectedVendor}
            isActing={integrations.isActing}
            savedAt={integrations.draftSavedAt}
            values={integrations.draftValues}
            onDiscard={() => {
              integrations.discardDraft(integrations.selectedVendor!);
              setOauthSecret("");
            }}
            onInstall={() => void install()}
            onOauthSecretChange={setOauthSecret}
            onValuesChange={integrations.updateDraft}
          />
        )
      ) : null}
      <ConnectionDeleteDialog
        connection={connectionPendingDelete}
        errorMessage={integrations.actionErrorMessage}
        isDeleting={integrations.isActing}
        vendorName={integrations.selectedVendor?.displayName ?? activeVendor}
        onConfirm={deleteConnection}
        onOpenChange={(open) => {
          if (!open) {
            integrations.clearActionError();
            setConnectionPendingDelete(null);
          }
        }}
      />
    </section>
  );
});

function InstallVendorForm({
  isActing,
  oauthSecret,
  onDiscard,
  onInstall,
  onOauthSecretChange,
  onValuesChange,
  savedAt,
  values,
  vendor,
}: {
  isActing: boolean;
  oauthSecret: string;
  onDiscard: () => void;
  onInstall: () => void;
  onOauthSecretChange: (value: string) => void;
  onValuesChange: (patch: Partial<typeof values>) => void;
  savedAt: string | null;
  values: {
    authKind: CuratedAuthKind | "";
    instanceUrl: string;
    oauthClientId: string;
    oauthTenant: string;
  };
  vendor: CuratedVendorDetail;
}) {
  const saved = formatIntegrationDate(savedAt);
  const needsOauth = values.authKind === "oauth2";
  const canInstall =
    values.authKind !== "" &&
    (!vendor.requiresInstanceUrl || values.instanceUrl.trim() !== "") &&
    (!needsOauth ||
      (values.oauthClientId.trim() !== "" && oauthSecret !== "")) &&
    (!vendor.requiresOauthTenant || values.oauthTenant.trim() !== "");
  return (
    <div className="max-w-3xl border">
      <div className="flex flex-wrap items-start justify-between gap-3 p-4 sm:p-5">
        <div>
          <h2 className="font-medium">Configure vendor</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            Choose how Eylo authorizes requests. Secrets stay out of the
            resumable browser draft.
          </p>
        </div>
        {savedAt ? (
          <time
            className="text-xs text-muted-foreground"
            dateTime={saved.title}
          >
            Draft saved {saved.label}
          </time>
        ) : null}
      </div>
      <Separator />
      <div className="space-y-5 p-4 sm:p-5">
        <FormField
          label="Authorization method"
          htmlFor="integration-auth-kind"
          required
        >
          <Select
            value={values.authKind || null}
            onValueChange={(value) =>
              onValuesChange({
                authKind: (value ?? "") as CuratedAuthKind | "",
              })
            }
          >
            <SelectTrigger id="integration-auth-kind" className="w-full">
              <SelectValue>
                {values.authKind
                  ? INTEGRATION_AUTH_LABELS[values.authKind]
                  : "Choose an authorization method"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {(vendor.authKinds ?? []).map((kind) => (
                <SelectItem key={kind} value={kind}>
                  {INTEGRATION_AUTH_LABELS[kind]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FormField>
        {vendor.requiresInstanceUrl ? (
          <FormField
            label={vendor.instanceUrlLabel ?? "Instance URL"}
            htmlFor="integration-instance-url"
            required
          >
            <Input
              id="integration-instance-url"
              type="url"
              placeholder={
                vendor.instanceUrlPlaceholder ?? "https://example.com"
              }
              value={values.instanceUrl}
              onChange={(event) =>
                onValuesChange({ instanceUrl: event.target.value })
              }
            />
          </FormField>
        ) : null}
        {needsOauth ? (
          <>
            <FormField
              label="OAuth client ID"
              htmlFor="integration-oauth-client-id"
              required
            >
              <Input
                id="integration-oauth-client-id"
                value={values.oauthClientId}
                onChange={(event) =>
                  onValuesChange({ oauthClientId: event.target.value })
                }
              />
            </FormField>
            <FormField
              label="OAuth client secret"
              htmlFor="integration-oauth-secret"
              hint="Entered only for this save; never persisted in the local draft."
              required
            >
              <Input
                id="integration-oauth-secret"
                type="password"
                autoComplete="new-password"
                value={oauthSecret}
                onChange={(event) => onOauthSecretChange(event.target.value)}
              />
            </FormField>
            {vendor.requiresOauthTenant ? (
              <FormField
                label="OAuth tenant"
                htmlFor="integration-oauth-tenant"
                required
              >
                <Input
                  id="integration-oauth-tenant"
                  value={values.oauthTenant}
                  onChange={(event) =>
                    onValuesChange({ oauthTenant: event.target.value })
                  }
                />
              </FormField>
            ) : null}
          </>
        ) : null}
      </div>
      <Separator />
      <div className="flex flex-wrap justify-end gap-2 p-4 sm:p-5">
        <Button variant="ghost" disabled={isActing} onClick={onDiscard}>
          <RotateCcw aria-hidden="true" />
          Start new
        </Button>
        <Button disabled={!canInstall || isActing} onClick={onInstall}>
          {isActing ? "Saving…" : "Install vendor"}
        </Button>
      </div>
    </div>
  );
}

function InstalledVendor({
  apiKey,
  connections,
  isActing,
  onApiKeyChange,
  onAuthorize,
  onConnect,
  onDeleteConnection,
  onPasswordChange,
  onToolModeChange,
  onUsernameChange,
  password,
  tools,
  username,
  vendor,
}: {
  apiKey: string;
  connections: CuratedConnection[];
  isActing: boolean;
  onApiKeyChange: (value: string) => void;
  onAuthorize: () => void;
  onConnect: () => void;
  onDeleteConnection: (connection: CuratedConnection) => void;
  onPasswordChange: (value: string) => void;
  onToolModeChange: (
    tool: CuratedInstalledTool,
    mode: "auto" | "disabled",
  ) => void;
  onUsernameChange: (value: string) => void;
  password: string;
  tools: CuratedInstalledTool[];
  username: string;
  vendor: CuratedVendorDetail;
}) {
  const { integrations } = useRootStore();
  const installation = integrations.selectedInstallation;
  if (!installation)
    return (
      <LoadFailure
        message="The installation record could not be loaded."
        onRetry={() => undefined}
      />
    );
  return (
    <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="min-w-0 space-y-5">
        <section className="border" aria-labelledby="tools-title">
          <div className="p-4 sm:p-5">
            <h2 id="tools-title" className="font-medium">
              Curated tools
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Tool policy is live. Disabled tools are not offered to Agents.
            </p>
          </div>
          <Separator />
          <div className="divide-y">
            {tools.map((tool) => (
              <div
                key={tool.id}
                className="grid min-w-0 gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_10rem] sm:items-center sm:p-5"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="break-words text-sm font-medium">
                      {tool.displayName}
                    </p>
                    <Badge variant="outline">
                      {tool.effect === "mutation"
                        ? "Changes data"
                        : "Read only"}
                    </Badge>
                  </div>
                  <p className="mt-1 break-words text-sm leading-6 text-muted-foreground">
                    {tool.description}
                  </p>
                  <code className="mt-1 block break-all text-xs text-muted-foreground">
                    {tool.agentName}
                  </code>
                </div>
                <Select
                  value={
                    tool.executionMode === "disabled" ? "disabled" : "auto"
                  }
                  disabled={isActing}
                  onValueChange={(value) =>
                    onToolModeChange(
                      tool,
                      value === "disabled" ? "disabled" : "auto",
                    )
                  }
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={`Execution mode for ${tool.displayName}`}
                  >
                    <SelectValue>
                      {tool.executionMode === "disabled"
                        ? "Disabled"
                        : "Automatic"}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Automatic</SelectItem>
                    <SelectItem value="disabled">Disabled</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
        </section>
      </div>
      <aside className="min-w-0 space-y-5">
        <section className="border">
          <div className="p-4">
            <h2 className="font-medium">Connection</h2>
            <Badge className="mt-2" variant="outline">
              {INTEGRATION_AUTH_LABELS[installation.authKind]}
            </Badge>
          </div>
          <Separator />
          <div className="space-y-4 p-4">
            {installation.authKind === "no_auth" ? (
              <p className="text-sm">No external credential required.</p>
            ) : installation.authKind === "oauth2" ? (
              <Button
                className="w-full"
                disabled={isActing}
                onClick={onAuthorize}
              >
                <Link2 aria-hidden="true" />
                Connect organization account
              </Button>
            ) : installation.authKind === "api_key" ? (
              <>
                <FormField label="API key" htmlFor="vendor-api-key" required>
                  <Input
                    id="vendor-api-key"
                    type="password"
                    autoComplete="off"
                    value={apiKey}
                    onChange={(event) => onApiKeyChange(event.target.value)}
                  />
                </FormField>
                <Button
                  className="w-full"
                  disabled={isActing || !apiKey}
                  onClick={onConnect}
                >
                  <KeyRound aria-hidden="true" />
                  Save connection
                </Button>
              </>
            ) : (
              <>
                <FormField label="Username" htmlFor="vendor-username" required>
                  <Input
                    id="vendor-username"
                    autoComplete="username"
                    value={username}
                    onChange={(event) => onUsernameChange(event.target.value)}
                  />
                </FormField>
                <FormField
                  label="Password or token"
                  htmlFor="vendor-password"
                  required
                >
                  <Input
                    id="vendor-password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => onPasswordChange(event.target.value)}
                  />
                </FormField>
                <Button
                  className="w-full"
                  disabled={isActing || !username || !password}
                  onClick={onConnect}
                >
                  <KeyRound aria-hidden="true" />
                  Save connection
                </Button>
              </>
            )}
          </div>
        </section>
        <section className="border">
          <div className="p-4">
            <h2 className="font-medium">Connections</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Credentials are never returned to this page.
            </p>
          </div>
          <Separator />
          {connections.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">
              No stored connections.
            </p>
          ) : (
            <div className="divide-y">
              {connections.map((connection) => (
                <ConnectionSummary
                  key={connection.id}
                  connection={connection}
                  disabled={isActing}
                  onDelete={() => onDeleteConnection(connection)}
                />
              ))}
            </div>
          )}
        </section>
        {vendor.homepageUrl ? (
          <a
            className="flex items-center gap-2 break-all text-sm text-muted-foreground underline underline-offset-4"
            href={vendor.homepageUrl}
            target="_blank"
            rel="noreferrer"
          >
            Vendor documentation{" "}
            <ExternalLink className="size-4 shrink-0" aria-hidden="true" />
          </a>
        ) : null}
      </aside>
    </div>
  );
}

function ConnectionSummary({
  connection,
  disabled,
  onDelete,
}: {
  connection: CuratedConnection;
  disabled: boolean;
  onDelete: () => void;
}) {
  const updated = formatIntegrationDate(
    connection.updatedAt ?? connection.createdAt,
  );
  return (
    <div className="min-w-0 space-y-1 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="break-words text-sm font-medium">
          {connection.owner.displayName}
        </p>
        <div className="flex flex-wrap items-center justify-end gap-1">
          <Badge variant="outline">
            {CONNECTION_KIND_LABELS[connection.connectionKind]}
          </Badge>
          <Badge
            variant={connection.status === "FAILED" ? "destructive" : "outline"}
          >
            {CONNECTION_STATUS_LABELS[connection.status]}
          </Badge>
          <Button
            type="button"
            variant="destructive"
            size="icon-xs"
            disabled={disabled}
            aria-label={`Delete ${connection.owner.displayName} connection`}
            title="Delete connection"
            onClick={onDelete}
          >
            <Trash2 aria-hidden="true" />
          </Button>
        </div>
      </div>
      <time className="text-xs text-muted-foreground" dateTime={updated.title}>
        Updated {updated.label}
      </time>
    </div>
  );
}

function FormField({
  children,
  hint,
  htmlFor,
  label,
  required,
}: {
  children: React.ReactNode;
  hint?: string;
  htmlFor: string;
  label: string;
  required?: boolean;
}) {
  return (
    <div className="min-w-0 space-y-2">
      <Label htmlFor={htmlFor}>
        {label}
        {required ? <span aria-hidden="true">*</span> : null}
      </Label>
      {hint ? (
        <p className="text-xs leading-5 text-muted-foreground">{hint}</p>
      ) : null}
      {children}
    </div>
  );
}
function LoadFailure({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="border py-12 text-center" role="alert">
      <p className="text-sm">{message}</p>
      <Button className="mt-4" variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
function openAuthorizationPopup(
  url: string,
  expectedOrigin: string,
  expectedVendor: string,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const popup = window.open(
      url,
      "eylo_curated_oauth",
      "width=600,height=720,left=200,top=80",
    );
    if (!popup) {
      reject(new Error("Popup blocked. Allow popups and try again."));
      return;
    }
    const finish = (error?: Error) => {
      window.removeEventListener("message", onMessage);
      window.clearInterval(poll);
      if (error) reject(error);
      else resolve();
    };
    const onMessage = (event: MessageEvent) => {
      if (event.source !== popup || event.origin !== expectedOrigin) return;
      const data = event.data as {
        type?: string;
        ok?: boolean;
        vendor?: string;
        error?: string;
      };
      if (data.type !== "eylo:curated-oauth" || data.vendor !== expectedVendor)
        return;
      finish(
        data.ok ? undefined : new Error(data.error || "Authorization failed."),
      );
    };
    window.addEventListener("message", onMessage);
    const poll = window.setInterval(() => {
      if (popup.closed) finish(new Error("Authorization window was closed."));
    }, 750);
  });
}

export { IntegrationVendorPage };
