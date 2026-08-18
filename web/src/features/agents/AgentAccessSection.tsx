import { BookOpen, Box, Plus, Search, Trash2 } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import type { AgentAccessStore } from "@/features/agents/agent-access.store";
import { formatAgentEnum } from "@/features/agents/agent-formatters";
import type {
  AgentKnowledgeAccess,
  AgentKnowledgebaseGrant,
} from "@/features/agents/agents.types";
import {
  providerCollectionPath,
  withReturnContext,
} from "@/features/providers/provider-navigation";
import { cn } from "@/lib/utils";

interface AgentAccessSectionProps {
  agentId: string;
  organizationId: string;
}

const AgentAccessSection = observer(function AgentAccessSection({
  agentId,
  organizationId,
}: AgentAccessSectionProps) {
  const { agents } = useRootStore();
  const access = agents.access;
  const [knowledgeDialogOpen, setKnowledgeDialogOpen] = useState(false);
  const [editingKnowledgeGrant, setEditingKnowledgeGrant] =
    useState<AgentKnowledgebaseGrant | null>(null);
  const [sandboxDialogOpen, setSandboxDialogOpen] = useState(false);

  useEffect(() => {
    void access.load(organizationId, agentId);
  }, [access, agentId, organizationId]);

  const hasKnowledgeState =
    access.knowledgebases.length > 0 || access.knowledgebaseGrants.length > 0;
  const hasSandboxState =
    access.sandboxConfigs.length > 0 || access.sandboxGrant !== null;

  function openKnowledgeDialog(grant: AgentKnowledgebaseGrant | null): void {
    access.clearActionError();
    setEditingKnowledgeGrant(grant);
    setKnowledgeDialogOpen(true);
  }

  function openSandboxDialog(): void {
    access.clearActionError();
    setSandboxDialogOpen(true);
  }

  return (
    <div className="space-y-5">
      {access.actionErrorMessage !== null ? (
        <p
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          role="alert"
        >
          {access.actionErrorMessage}
        </p>
      ) : null}
      <AccessCard
        title="Knowledgebases"
        description="Grant only the knowledge this Agent may read or write."
        action={
          <Button
            type="button"
            variant="outline"
            onClick={() => openKnowledgeDialog(null)}
          >
            <Plus aria-hidden="true" />
            Grant knowledgebase
          </Button>
        }
      >
        {access.isKnowledgeLoading && !hasKnowledgeState ? (
          <p className="text-sm text-muted-foreground">
            Loading knowledge access…
          </p>
        ) : access.knowledgeErrorMessage !== null && !hasKnowledgeState ? (
          <AccessLoadError
            message={access.knowledgeErrorMessage}
            onRetry={() => void access.load(organizationId, agentId, true)}
          />
        ) : access.knowledgebaseGrants.length === 0 ? (
          <AccessEmpty>No knowledgebase access granted.</AccessEmpty>
        ) : (
          <div className="space-y-3">
            {access.knowledgeErrorMessage !== null ? (
              <StaleAccessNotice
                label="knowledge access"
                onRetry={() => void access.load(organizationId, agentId, true)}
              />
            ) : null}
            <div className="divide-y border-y">
              {access.knowledgebaseGrants.map((grant) => {
                const knowledgebase = access.knowledgebaseFor(
                  grant.knowledgebase_id,
                );
                const name = knowledgebase?.name ?? grant.knowledgebase_id;
                return (
                  <div
                    key={grant.id}
                    className="flex flex-wrap items-center justify-between gap-4 py-3"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <BookOpen className="size-4" aria-hidden="true" />
                        <p className="truncate text-sm font-medium">{name}</p>
                        <Badge variant="outline">
                          {grant.access === "read_write"
                            ? "Read + write"
                            : "Read"}
                        </Badge>
                      </div>
                      {knowledgebase === null ? (
                        <p className="mt-1 truncate text-xs text-muted-foreground">
                          Knowledgebase details unavailable
                        </p>
                      ) : (
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          <Badge variant="outline">
                            {formatAgentEnum(knowledgebase.vendor)}
                          </Badge>
                          <Badge variant="outline">
                            {formatAgentEnum(knowledgebase.scope)}
                          </Badge>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={access.isActing}
                        onClick={() => openKnowledgeDialog(grant)}
                      >
                        Change
                      </Button>
                      <Button
                        type="button"
                        size="icon-sm"
                        variant="ghost"
                        disabled={access.isActing}
                        aria-label={`Revoke ${name}`}
                        title="Revoke knowledgebase access"
                        onClick={() =>
                          void access.revokeKnowledgebase(
                            organizationId,
                            agentId,
                            grant.knowledgebase_id,
                          )
                        }
                      >
                        <Trash2 aria-hidden="true" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </AccessCard>

      <AccessCard
        title="Sandbox"
        description="Grant bounded no-egress code execution through one explicit ready config."
        action={
          <Button type="button" variant="outline" onClick={openSandboxDialog}>
            <Box aria-hidden="true" />
            {access.sandboxGrant === null ? "Grant sandbox" : "Change sandbox"}
          </Button>
        }
      >
        {access.isSandboxLoading && !hasSandboxState ? (
          <p className="text-sm text-muted-foreground">
            Loading sandbox access…
          </p>
        ) : access.sandboxErrorMessage !== null && !hasSandboxState ? (
          <AccessLoadError
            message={access.sandboxErrorMessage}
            onRetry={() => void access.load(organizationId, agentId, true)}
          />
        ) : access.sandboxGrant === null ? (
          <AccessEmpty>No sandbox execution granted.</AccessEmpty>
        ) : (
          <div className="space-y-3">
            {access.sandboxErrorMessage !== null ? (
              <StaleAccessNotice
                label="sandbox access"
                onRetry={() => void access.load(organizationId, agentId, true)}
              />
            ) : null}
            <div className="flex flex-wrap items-center justify-between gap-4 border-y py-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Box className="size-4" aria-hidden="true" />
                  <p className="truncate text-sm font-medium">
                    {access.sandboxConfigFor(
                      access.sandboxGrant.sandbox_provider_config_id,
                    )?.name ?? access.sandboxGrant.sandbox_provider_config_id}
                  </p>
                  <Badge variant="outline">Run</Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Config revision{" "}
                  {access.sandboxGrant.sandbox_provider_config_revision}
                  {access.sandboxGrant.max_sessions === null
                    ? " · organization session limit"
                    : ` · max ${access.sandboxGrant.max_sessions} sessions`}
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={access.isActing}
                onClick={() =>
                  void access.revokeSandbox(organizationId, agentId)
                }
              >
                <Trash2 aria-hidden="true" />
                Revoke
              </Button>
            </div>
          </div>
        )}
      </AccessCard>

      <KnowledgeGrantDialog
        access={access}
        agentId={agentId}
        editingGrant={editingKnowledgeGrant}
        open={knowledgeDialogOpen}
        organizationId={organizationId}
        onOpenChange={setKnowledgeDialogOpen}
      />
      <SandboxGrantDialog
        access={access}
        agentId={agentId}
        open={sandboxDialogOpen}
        organizationId={organizationId}
        onOpenChange={setSandboxDialogOpen}
      />
    </div>
  );
});

const KnowledgeGrantDialog = observer(function KnowledgeGrantDialog({
  access,
  agentId,
  editingGrant,
  onOpenChange,
  open,
  organizationId,
}: {
  access: AgentAccessStore;
  agentId: string;
  editingGrant: AgentKnowledgebaseGrant | null;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  organizationId: string;
}) {
  const [search, setSearch] = useState("");
  const [knowledgebaseId, setKnowledgebaseId] = useState<string | null>(null);
  const [knowledgeAccess, setKnowledgeAccess] = useState<
    AgentKnowledgeAccess | ""
  >("");
  const grantedIds = useMemo(
    () =>
      new Set(
        access.knowledgebaseGrants.map((grant) => grant.knowledgebase_id),
      ),
    [access.knowledgebaseGrants],
  );
  const selectedKnowledgebase =
    knowledgebaseId === null ? null : access.knowledgebaseFor(knowledgebaseId);
  const normalizedSearch = search.trim().toLowerCase();
  const options = access.knowledgebases.filter(
    (knowledgebase) =>
      (editingGrant?.knowledgebase_id === knowledgebase.id ||
        !grantedIds.has(knowledgebase.id)) &&
      (normalizedSearch === "" ||
        `${knowledgebase.name} ${knowledgebase.vendor} ${knowledgebase.scope}`
          .toLowerCase()
          .includes(normalizedSearch)),
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    setSearch("");
    setKnowledgebaseId(editingGrant?.knowledgebase_id ?? null);
    setKnowledgeAccess(editingGrant?.access ?? "");
  }, [editingGrant, open]);

  async function save(): Promise<void> {
    if (knowledgebaseId === null || knowledgeAccess === "") {
      return;
    }
    const saved = await access.grantKnowledgebase(
      organizationId,
      agentId,
      knowledgebaseId,
      knowledgeAccess,
    );
    if (saved) {
      onOpenChange(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader className="pr-8">
          <DialogTitle>
            {editingGrant === null
              ? "Grant knowledgebase"
              : "Change knowledge access"}
          </DialogTitle>
          <DialogDescription>
            Choose one knowledgebase and an explicit access mode. Regranting
            changes the current runtime authority.
          </DialogDescription>
        </DialogHeader>

        {access.actionErrorMessage !== null ? (
          <p className="text-sm text-destructive" role="alert">
            {access.actionErrorMessage}
          </p>
        ) : null}

        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            className="pl-9"
            aria-label="Search knowledgebases"
            placeholder="Search knowledgebases"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>

        <div className="max-h-56 min-h-32 divide-y overflow-y-auto border">
          {options.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No ungranted knowledgebase matches this search.
            </p>
          ) : (
            options.map((knowledgebase) => (
              <button
                key={knowledgebase.id}
                type="button"
                className={cn(
                  "grid w-full grid-cols-[1fr_auto] gap-3 p-3 text-left hover:bg-muted focus-visible:outline-2",
                  knowledgebaseId === knowledgebase.id && "bg-muted",
                )}
                onClick={() => {
                  setKnowledgebaseId(knowledgebase.id);
                  if (
                    !knowledgebase.writable &&
                    knowledgeAccess === "read_write"
                  ) {
                    setKnowledgeAccess("");
                  }
                }}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">
                    {knowledgebase.name}
                  </span>
                  <span className="mt-1 flex flex-wrap gap-1.5">
                    <Badge variant="outline">
                      {formatAgentEnum(knowledgebase.vendor)}
                    </Badge>
                    <Badge variant="outline">
                      {formatAgentEnum(knowledgebase.scope)}
                    </Badge>
                  </span>
                </span>
                <span className="text-xs text-muted-foreground">
                  {knowledgebase.writable ? "Writable" : "Read-only"}
                </span>
              </button>
            ))
          )}
        </div>

        <fieldset className="space-y-2" disabled={knowledgebaseId === null}>
          <legend className="text-sm font-medium">Access mode</legend>
          <div className="grid grid-cols-2 gap-2">
            <AccessModeButton
              active={knowledgeAccess === "read"}
              label="Read"
              onClick={() => setKnowledgeAccess("read")}
            />
            <AccessModeButton
              active={knowledgeAccess === "read_write"}
              disabled={selectedKnowledgebase?.writable !== true}
              label="Read + write"
              onClick={() => setKnowledgeAccess("read_write")}
            />
          </div>
          {selectedKnowledgebase !== null && !selectedKnowledgebase.writable ? (
            <p className="text-xs text-muted-foreground">
              This knowledgebase does not accept writes.
            </p>
          ) : null}
        </fieldset>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={
              knowledgebaseId === null ||
              knowledgeAccess === "" ||
              access.isActing
            }
            onClick={() => void save()}
          >
            {access.isActing ? "Saving…" : "Save access"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
});

const SandboxGrantDialog = observer(function SandboxGrantDialog({
  access,
  agentId,
  onOpenChange,
  open,
  organizationId,
}: {
  access: AgentAccessStore;
  agentId: string;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  organizationId: string;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [configId, setConfigId] = useState<string | null>(null);
  const [maxSessions, setMaxSessions] = useState("");
  const hasReadyConfig = access.sandboxConfigs.some((config) => config.ready);
  const selectedConfig =
    configId === null ? null : access.sandboxConfigFor(configId);
  const parsedMaxSessions = maxSessions === "" ? null : Number(maxSessions);
  const maxSessionsIsValid =
    parsedMaxSessions === null ||
    (Number.isInteger(parsedMaxSessions) &&
      parsedMaxSessions >= 1 &&
      parsedMaxSessions <= (selectedConfig?.config.maxSessions ?? 100));

  useEffect(() => {
    if (!open) {
      return;
    }
    setConfigId(access.sandboxGrant?.sandbox_provider_config_id ?? null);
    setMaxSessions(
      access.sandboxGrant?.max_sessions === null || access.sandboxGrant === null
        ? ""
        : String(access.sandboxGrant.max_sessions),
    );
  }, [access.sandboxGrant, open]);

  async function save(): Promise<void> {
    if (configId === null || !maxSessionsIsValid) {
      return;
    }
    const saved = await access.grantSandbox(
      organizationId,
      agentId,
      configId,
      parsedMaxSessions,
    );
    if (saved) {
      onOpenChange(false);
    }
  }

  function configureSandbox(): void {
    access.clearActionError();
    onOpenChange(false);
    void navigate(
      withReturnContext(
        providerCollectionPath(organizationId, "sandbox"),
        `${location.pathname}${location.search}`,
      ),
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader className="pr-8">
          <DialogTitle>Grant sandbox execution</DialogTitle>
          <DialogDescription>
            Select one ready no-egress sandbox config. V1 exposes only bounded
            run access.
          </DialogDescription>
        </DialogHeader>

        {access.actionErrorMessage !== null ? (
          <p className="text-sm text-destructive" role="alert">
            {access.actionErrorMessage}
          </p>
        ) : null}

        <div className="max-h-64 min-h-32 divide-y overflow-y-auto border">
          {access.sandboxConfigs.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No sandbox configs exist. Configure one under Providers first.
            </p>
          ) : (
            access.sandboxConfigs.map((config) => (
              <button
                key={config.id}
                type="button"
                disabled={!config.ready}
                className={cn(
                  "grid w-full grid-cols-[1fr_auto] gap-3 p-3 text-left hover:bg-muted focus-visible:outline-2 disabled:cursor-not-allowed disabled:bg-muted/50 disabled:text-muted-foreground",
                  configId === config.id && "bg-muted",
                )}
                onClick={() => setConfigId(config.id)}
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium">
                    {config.name}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {config.provider} · max {config.config.maxSessions} sessions
                  </span>
                </span>
                <span className="text-xs text-muted-foreground">
                  {config.ready ? "Ready" : "Not ready"}
                </span>
              </button>
            ))
          )}
        </div>

        {!hasReadyConfig ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border p-3">
            <p className="text-sm text-muted-foreground">
              A sandbox config must pass provider verification before it can be
              granted.
            </p>
            <Button type="button" variant="outline" onClick={configureSandbox}>
              Configure sandbox
            </Button>
          </div>
        ) : null}

        <div className="space-y-2">
          <Label htmlFor="agent-sandbox-max-sessions">
            Agent session limit
          </Label>
          <Input
            id="agent-sandbox-max-sessions"
            type="number"
            inputMode="numeric"
            min={1}
            max={selectedConfig?.config.maxSessions ?? 100}
            disabled={selectedConfig === null}
            placeholder="Use organization limit"
            value={maxSessions}
            onChange={(event) => setMaxSessions(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            {maxSessionsIsValid
              ? "Leave empty to use the selected config's organization limit."
              : `Enter a whole number from 1 to ${selectedConfig?.config.maxSessions ?? 100}.`}
          </p>
        </div>

        <div className="flex items-center justify-between border p-3 text-sm">
          <span>Access</span>
          <Badge variant="outline">Run · no network egress</Badge>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={
              selectedConfig?.ready !== true ||
              !maxSessionsIsValid ||
              access.isActing
            }
            onClick={() => void save()}
          >
            {access.isActing ? "Saving…" : "Save sandbox grant"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
});

function AccessModeButton({
  active,
  disabled = false,
  label,
  onClick,
}: {
  active: boolean;
  disabled?: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      variant={active ? "secondary" : "outline"}
      disabled={disabled}
      aria-pressed={active}
      onClick={onClick}
    >
      {label}
    </Button>
  );
}

function AccessCard({
  action,
  children,
  description,
  title,
}: {
  action?: React.ReactNode;
  children: React.ReactNode;
  description: string;
  title: string;
}) {
  return (
    <section className="border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-4 p-5">
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="text-sm leading-5 text-muted-foreground">
            {description}
          </p>
        </div>
        {action}
      </div>
      <Separator />
      <div className="p-5">{children}</div>
    </section>
  );
}

function AccessEmpty({ children }: { children: React.ReactNode }) {
  return (
    <p className="border border-dashed p-6 text-center text-sm text-muted-foreground">
      {children}
    </p>
  );
}

function AccessLoadError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div>
      <p className="text-sm text-destructive" role="alert">
        {message}
      </p>
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

function StaleAccessNotice({
  label,
  onRetry,
}: {
  label: string;
  onRetry: () => void;
}) {
  return (
    <div
      className="flex flex-wrap items-center justify-between gap-3 border p-3"
      role="status"
    >
      <p className="text-sm text-muted-foreground">
        Showing the last loaded {label}. Refresh failed.
      </p>
      <Button type="button" size="sm" variant="ghost" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

export { AgentAccessSection };
