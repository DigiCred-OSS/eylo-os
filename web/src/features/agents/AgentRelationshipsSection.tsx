import { Link2, Plug, Plus, Search, Trash2, Wrench } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { formatAgentEnum } from "@/features/agents/agent-formatters";
import type {
  Agent,
  AgentCuratedTool,
  Tool,
} from "@/features/agents/agents.types";

interface AgentRelationshipsSectionProps {
  agentId: string;
  organizationId: string;
}

const AgentRelationshipsSection = observer(function AgentRelationshipsSection({
  agentId,
  organizationId,
}: AgentRelationshipsSectionProps) {
  const { agents } = useRootStore();
  const relationships = agents.relationships;
  const owner = agents.form.serverAgent;
  const [toolDialogOpen, setToolDialogOpen] = useState(false);
  const [curatedToolDialogOpen, setCuratedToolDialogOpen] = useState(false);
  const [backgroundDialogOpen, setBackgroundDialogOpen] = useState(false);

  useEffect(() => {
    void relationships.load(organizationId, agentId);
  }, [agentId, organizationId, relationships]);

  return (
    <div className="space-y-5">
      {relationships.actionErrorMessage !== null ? (
        <div
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          role="alert"
        >
          {relationships.actionErrorMessage}
        </div>
      ) : null}

      <RelationshipCard
        title="Tools"
        description="Grant published tools to this Agent's next revision."
        action={
          !relationships.isToolsLoading &&
          relationships.toolsErrorMessage === null ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => setToolDialogOpen(true)}
            >
              <Plus aria-hidden="true" />
              Add tool
            </Button>
          ) : null
        }
      >
        {relationships.isToolsLoading ? (
          <p className="text-sm text-muted-foreground">Loading tools…</p>
        ) : relationships.toolsErrorMessage !== null ? (
          <RelationshipLoadFailure
            errorMessage={relationships.toolsErrorMessage}
            onRetry={() =>
              void relationships.load(organizationId, agentId, true)
            }
          />
        ) : relationships.assignedTools.length === 0 ? (
          <RelationshipEmpty>No tools assigned.</RelationshipEmpty>
        ) : (
          <div className="divide-y border-y">
            {relationships.assignedTools.map((tool) => (
              <div
                key={tool.id}
                className="flex items-center justify-between gap-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {tool.displayName || tool.name}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {tool.description}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Remove ${tool.displayName || tool.name}`}
                  title="Remove tool"
                  disabled={relationships.isActing}
                  onClick={() =>
                    void relationships.removeTool(
                      organizationId,
                      agentId,
                      tool.id,
                    )
                  }
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </RelationshipCard>

      <RelationshipCard
        title="Integration tools"
        description="Choose the exact installed-vendor tools for this Agent's next published revision."
        action={
          !relationships.isCuratedToolsLoading &&
          relationships.curatedToolsErrorMessage === null &&
          relationships.availableCuratedTools.length > 0 ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => setCuratedToolDialogOpen(true)}
            >
              <Plug aria-hidden="true" />
              Manage integration tools
            </Button>
          ) : null
        }
      >
        {relationships.isCuratedToolsLoading ? (
          <p className="text-sm text-muted-foreground">
            Loading integration tools…
          </p>
        ) : relationships.curatedToolsErrorMessage !== null ? (
          <RelationshipLoadFailure
            errorMessage={relationships.curatedToolsErrorMessage}
            onRetry={() =>
              void relationships.load(organizationId, agentId, true)
            }
          />
        ) : relationships.availableCuratedTools.length === 0 ? (
          <RelationshipEmpty>
            No vendors are installed. Configure one in{" "}
            <Link
              className="font-medium text-foreground underline underline-offset-4"
              to={`/org/${organizationId}/integrations`}
            >
              Integrations
            </Link>
            .
          </RelationshipEmpty>
        ) : relationships.assignedCuratedTools.length === 0 ? (
          <RelationshipEmpty>No integration tools assigned.</RelationshipEmpty>
        ) : (
          <div className="divide-y border-y">
            {relationships.assignedCuratedTools.map((tool) => (
              <div
                key={tool.id}
                className="flex min-w-0 items-center justify-between gap-4 py-3"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="break-words text-sm font-medium">
                      {tool.displayName}
                    </p>
                    <Badge variant="outline">{tool.vendorDisplayName}</Badge>
                    <Badge variant="outline">
                      {formatAgentEnum(tool.effect)}
                    </Badge>
                    {tool.executionMode === "disabled" ? (
                      <Badge variant="outline">Disabled by policy</Badge>
                    ) : null}
                  </div>
                  <p className="mt-1 break-words text-xs leading-5 text-muted-foreground">
                    {tool.description}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="shrink-0"
                  aria-label={`Remove ${tool.displayName}`}
                  title="Remove integration tool"
                  disabled={relationships.isActing}
                  onClick={() =>
                    void relationships.removeCuratedTool(
                      organizationId,
                      agentId,
                      tool,
                    )
                  }
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </RelationshipCard>

      <RelationshipCard
        title="Background Agents"
        description="Attach background work explicitly. New attachments start disabled."
        action={
          owner?.kind === "CONVERSATIONAL" &&
          !relationships.isBackgroundsLoading &&
          relationships.backgroundsErrorMessage === null ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => setBackgroundDialogOpen(true)}
            >
              <Plus aria-hidden="true" />
              Add background Agent
            </Button>
          ) : null
        }
      >
        {owner?.kind !== "CONVERSATIONAL" ? (
          <RelationshipEmpty>
            Not applicable. Background Agents cannot own chained background
            attachments.
          </RelationshipEmpty>
        ) : relationships.isBackgroundsLoading ? (
          <p className="text-sm text-muted-foreground">
            Loading background Agents…
          </p>
        ) : relationships.backgroundsErrorMessage !== null ? (
          <RelationshipLoadFailure
            errorMessage={relationships.backgroundsErrorMessage}
            onRetry={() =>
              void relationships.load(organizationId, agentId, true)
            }
          />
        ) : relationships.attachments.length === 0 ? (
          <RelationshipEmpty>No background Agents attached.</RelationshipEmpty>
        ) : (
          <div className="divide-y border-y">
            {relationships.attachments.map((attachment) => {
              const background = relationships.availableBackgroundAgents.find(
                (candidate) => candidate.id === attachment.background_agent_id,
              );
              const name = background?.name ?? attachment.background_agent_id;

              return (
                <div
                  key={attachment.id}
                  className="flex items-center justify-between gap-4 py-3"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="truncate text-sm font-medium">{name}</p>
                      <Badge variant="outline">
                        {attachment.enabled ? "Enabled" : "Disabled"}
                      </Badge>
                    </div>
                    <p className="truncate text-xs text-muted-foreground">
                      {background?.description ?? "Attached background Agent"}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Switch
                      checked={attachment.enabled}
                      disabled={relationships.isActing}
                      aria-label={`${attachment.enabled ? "Disable" : "Enable"} ${name}`}
                      onCheckedChange={(checked) =>
                        void relationships.setBackgroundAgentEnabled(
                          organizationId,
                          agentId,
                          attachment.background_agent_id,
                          checked,
                        )
                      }
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Detach ${name}`}
                      title="Detach background Agent"
                      disabled={relationships.isActing}
                      onClick={() =>
                        void relationships.detachBackgroundAgent(
                          organizationId,
                          agentId,
                          attachment.background_agent_id,
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
        )}
      </RelationshipCard>

      <ToolPickerDialog
        open={toolDialogOpen}
        tools={relationships.availableTools}
        assignedTools={relationships.assignedTools}
        isActing={relationships.isActing}
        systemCatalogToolIds={relationships.systemCatalogToolIds}
        onOpenChange={setToolDialogOpen}
        onSelect={async (toolId) => {
          const saved = await relationships.assignTool(
            organizationId,
            agentId,
            toolId,
          );
          if (saved) {
            setToolDialogOpen(false);
          }
        }}
      />

      {curatedToolDialogOpen ? (
        <IntegrationToolPickerDialog
          open
          tools={relationships.availableCuratedTools}
          assignedTools={relationships.assignedCuratedTools}
          errorMessage={relationships.actionErrorMessage}
          isActing={relationships.isActing}
          onOpenChange={setCuratedToolDialogOpen}
          onApply={(tools) =>
            relationships.replaceCuratedTools(organizationId, agentId, tools)
          }
        />
      ) : null}

      <BackgroundAgentPickerDialog
        open={backgroundDialogOpen}
        agents={relationships.availableBackgroundAgents}
        attachedIds={relationships.attachments.map(
          (attachment) => attachment.background_agent_id,
        )}
        isActing={relationships.isActing}
        onOpenChange={setBackgroundDialogOpen}
        onSelect={async (backgroundAgentId) => {
          const saved = await relationships.attachBackgroundAgent(
            organizationId,
            agentId,
            backgroundAgentId,
          );
          if (saved) {
            setBackgroundDialogOpen(false);
          }
        }}
      />
    </div>
  );
});

function ToolPickerDialog({
  assignedTools,
  isActing,
  onOpenChange,
  onSelect,
  open,
  systemCatalogToolIds,
  tools,
}: {
  assignedTools: Tool[];
  isActing: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (toolId: string) => Promise<void>;
  open: boolean;
  systemCatalogToolIds: ReadonlySet<string>;
  tools: Tool[];
}) {
  const [search, setSearch] = useState("");
  const assignedIds = useMemo(
    () => new Set(assignedTools.map((tool) => tool.id)),
    [assignedTools],
  );
  const options = tools.filter((tool) => !assignedIds.has(tool.id));
  const filteredOptions = filterTools(options, search);

  return (
    <RelationshipPickerDialog
      description="Choose a published organization tool or an available system tool. Assignment changes the Agent draft version."
      emptyMessage="No unassigned tools match this search."
      open={open}
      search={search}
      title="Add tool"
      onOpenChange={(nextOpen) => {
        onOpenChange(nextOpen);
        if (nextOpen) setSearch("");
      }}
      onSearchChange={setSearch}
    >
      {filteredOptions.map((tool) => {
        const isPublished = tool.publishedRevision != null;
        const isSystemCatalogTool = systemCatalogToolIds.has(tool.id);
        const isAssignable = isPublished || isSystemCatalogTool;
        return (
          <button
            key={tool.id}
            className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 p-3 text-left hover:bg-muted focus-visible:outline-2 disabled:cursor-not-allowed disabled:bg-muted/50 disabled:text-muted-foreground"
            type="button"
            disabled={!isAssignable || isActing}
            onClick={() => void onSelect(tool.id)}
          >
            <Wrench className="size-4" aria-hidden="true" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">
                {tool.displayName || tool.name}
              </span>
              <span className="block truncate text-xs text-muted-foreground">
                {tool.description}
              </span>
            </span>
            <span className="text-xs text-muted-foreground">
              {isPublished
                ? `Revision ${tool.publishedRevision}`
                : isSystemCatalogTool
                  ? "System tool"
                  : "Not published"}
            </span>
          </button>
        );
      })}
    </RelationshipPickerDialog>
  );
}

function BackgroundAgentPickerDialog({
  agents,
  attachedIds,
  isActing,
  onOpenChange,
  onSelect,
  open,
}: {
  agents: Agent[];
  attachedIds: string[];
  isActing: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (agentId: string) => Promise<void>;
  open: boolean;
}) {
  const [search, setSearch] = useState("");
  const attached = useMemo(() => new Set(attachedIds), [attachedIds]);
  const normalizedSearch = search.trim().toLowerCase();
  const options = agents.filter(
    (agent) =>
      !attached.has(agent.id) &&
      (normalizedSearch === "" ||
        `${agent.name} ${agent.description ?? ""}`
          .toLowerCase()
          .includes(normalizedSearch)),
  );

  return (
    <RelationshipPickerDialog
      description="Attachments start disabled. Enable one after reviewing its configuration."
      emptyMessage="No unattached background Agents match this search."
      open={open}
      search={search}
      title="Add background Agent"
      onOpenChange={(nextOpen) => {
        onOpenChange(nextOpen);
        if (nextOpen) setSearch("");
      }}
      onSearchChange={setSearch}
    >
      {options.map((agent) => (
        <button
          key={agent.id}
          className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 p-3 text-left hover:bg-muted focus-visible:outline-2 disabled:cursor-not-allowed disabled:bg-muted/50"
          type="button"
          disabled={isActing}
          onClick={() => void onSelect(agent.id)}
        >
          <Link2 className="size-4" aria-hidden="true" />
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">
              {agent.name}
            </span>
            <span className="block truncate text-xs text-muted-foreground">
              {agent.description || "No description"}
            </span>
          </span>
          <Badge variant="outline">{formatAgentEnum(agent.lifecycle)}</Badge>
        </button>
      ))}
    </RelationshipPickerDialog>
  );
}

function IntegrationToolPickerDialog({
  assignedTools,
  errorMessage,
  isActing,
  onApply,
  onOpenChange,
  open,
  tools,
}: {
  assignedTools: AgentCuratedTool[];
  errorMessage: string | null;
  isActing: boolean;
  onApply: (tools: AgentCuratedTool[]) => Promise<boolean>;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  tools: AgentCuratedTool[];
}) {
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    () => new Set(assignedTools.map((tool) => tool.id)),
  );
  const [saveAttempted, setSaveAttempted] = useState(false);
  const assignedIds = useMemo(
    () => new Set(assignedTools.map((tool) => tool.id)),
    [assignedTools],
  );
  const normalizedSearch = search.trim().toLowerCase();
  const options = tools.filter(
    (tool) =>
      normalizedSearch === "" ||
      `${tool.displayName} ${tool.description} ${tool.vendorDisplayName} ${tool.effect}`
        .toLowerCase()
        .includes(normalizedSearch),
  );
  const groupedTools = useMemo(() => groupToolsByVendor(options), [options]);
  const selectionChanged =
    selectedIds.size !== assignedIds.size ||
    Array.from(selectedIds).some((id) => !assignedIds.has(id));

  function changeOpen(nextOpen: boolean): void {
    if (!nextOpen && isActing) return;
    onOpenChange(nextOpen);
  }

  function setToolSelected(tool: AgentCuratedTool, selected: boolean): void {
    if (tool.executionMode === "disabled" && selected) return;
    setSelectedIds((current) => {
      const next = new Set(current);
      if (selected) next.add(tool.id);
      else next.delete(tool.id);
      return next;
    });
  }

  function selectReadable(vendorTools: AgentCuratedTool[]): void {
    setSelectedIds((current) => {
      const next = new Set(current);
      for (const tool of vendorTools) {
        if (tool.effect === "read" && tool.executionMode !== "disabled") {
          next.add(tool.id);
        }
      }
      return next;
    });
  }

  function clearVendor(vendorTools: AgentCuratedTool[]): void {
    setSelectedIds((current) => {
      const next = new Set(current);
      for (const tool of vendorTools) next.delete(tool.id);
      return next;
    });
  }

  async function applySelection(): Promise<void> {
    setSaveAttempted(true);
    const selectedTools = tools.filter((tool) => selectedIds.has(tool.id));
    if (await onApply(selectedTools)) changeOpen(false);
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className="flex max-h-[calc(100dvh-2rem)] flex-col overflow-hidden sm:max-w-2xl">
        <DialogHeader className="shrink-0 pr-8">
          <DialogTitle>Assign integration tools</DialogTitle>
          <DialogDescription>
            Select the exact tools this Agent may use. Changes update the draft;
            publish the Agent to use them in new conversations.
          </DialogDescription>
        </DialogHeader>
        <div className="relative shrink-0">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            className="pl-9"
            aria-label="Search integration tools"
            placeholder="Search tools, vendors, or effects"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden border">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
            <span>{selectedIds.size} selected</span>
            <span>{assignedIds.size} assigned now</span>
          </div>
          <div className="min-h-40 overflow-y-auto">
            {groupedTools.length === 0 ? (
              <p className="p-6 text-center text-sm text-muted-foreground">
                No integration tools match this search.
              </p>
            ) : (
              groupedTools.map((group) => (
                <section
                  key={group.vendor}
                  aria-labelledby={`${group.vendor}-tools`}
                >
                  <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-2 border-b bg-background px-3 py-2">
                    <h3
                      id={`${group.vendor}-tools`}
                      className="text-sm font-medium"
                    >
                      {group.vendorDisplayName}
                    </h3>
                    <div className="flex items-center gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="xs"
                        disabled={isActing}
                        onClick={() => selectReadable(group.tools)}
                      >
                        Select read
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="xs"
                        disabled={isActing}
                        onClick={() => clearVendor(group.tools)}
                      >
                        Clear
                      </Button>
                    </div>
                  </div>
                  <div className="divide-y">
                    {group.tools.map((tool) => {
                      const selected = selectedIds.has(tool.id);
                      const unavailable =
                        tool.executionMode === "disabled" && !selected;
                      return (
                        <label
                          key={tool.id}
                          className="grid cursor-pointer grid-cols-[auto_minmax(0,1fr)] gap-3 p-3 hover:bg-muted/50 has-data-disabled:cursor-not-allowed has-data-disabled:bg-muted/30"
                        >
                          <Checkbox
                            className="mt-0.5"
                            checked={selected}
                            disabled={isActing || unavailable}
                            onCheckedChange={(checked) =>
                              setToolSelected(tool, checked)
                            }
                          />
                          <span className="min-w-0">
                            <span className="flex flex-wrap items-center gap-2">
                              <span className="break-words text-sm font-medium">
                                {tool.displayName}
                              </span>
                              <Badge variant="outline">
                                {formatAgentEnum(tool.effect)}
                              </Badge>
                              <Badge variant="outline">
                                {assignedIds.has(tool.id)
                                  ? "Assigned"
                                  : "Available"}
                              </Badge>
                              {tool.executionMode === "disabled" ? (
                                <Badge variant="outline">
                                  Disabled by policy
                                </Badge>
                              ) : null}
                            </span>
                            <span className="mt-1 block break-words text-xs leading-5 text-muted-foreground">
                              {tool.description}
                            </span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </section>
              ))
            )}
          </div>
        </div>
        {saveAttempted && errorMessage !== null ? (
          <p className="text-sm text-destructive" role="alert">
            {errorMessage}
          </p>
        ) : null}
        <DialogFooter className="shrink-0">
          <Button
            type="button"
            variant="outline"
            disabled={isActing}
            onClick={() => changeOpen(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={isActing || !selectionChanged}
            onClick={() => void applySelection()}
          >
            {isActing ? "Applying…" : "Apply tool assignments"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface CuratedToolGroup {
  tools: AgentCuratedTool[];
  vendor: string;
  vendorDisplayName: string;
}

function groupToolsByVendor(tools: AgentCuratedTool[]): CuratedToolGroup[] {
  const groups = new Map<string, CuratedToolGroup>();
  for (const tool of tools) {
    const group = groups.get(tool.vendor) ?? {
      tools: [],
      vendor: tool.vendor,
      vendorDisplayName: tool.vendorDisplayName,
    };
    group.tools.push(tool);
    groups.set(tool.vendor, group);
  }
  return Array.from(groups.values()).sort((left, right) =>
    left.vendorDisplayName.localeCompare(right.vendorDisplayName),
  );
}

function RelationshipPickerDialog({
  children,
  description,
  emptyMessage,
  onOpenChange,
  onSearchChange,
  open,
  search,
  title,
}: {
  children: React.ReactNode;
  description: string;
  emptyMessage: string;
  onOpenChange: (open: boolean) => void;
  onSearchChange: (value: string) => void;
  open: boolean;
  search: string;
  title: string;
}) {
  const hasOptions = Array.isArray(children)
    ? children.length > 0
    : children != null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader className="pr-8">
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            className="pl-9"
            aria-label={`Search ${title}`}
            placeholder="Search"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </div>
        <div className="max-h-80 min-h-36 divide-y overflow-y-auto border">
          {hasOptions ? (
            children
          ) : (
            <p className="p-6 text-center text-sm text-muted-foreground">
              {emptyMessage}
            </p>
          )}
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RelationshipCard({
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

function RelationshipEmpty({ children }: { children: React.ReactNode }) {
  return (
    <p className="border border-dashed p-6 text-center text-sm text-muted-foreground">
      {children}
    </p>
  );
}

function RelationshipLoadFailure({
  errorMessage,
  onRetry,
}: {
  errorMessage: string;
  onRetry: () => void;
}) {
  return (
    <div>
      <p className="text-sm text-destructive" role="alert">
        {errorMessage}
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

function filterTools(tools: readonly Tool[], search: string): Tool[] {
  const normalizedSearch = search.trim().toLowerCase();
  return normalizedSearch === ""
    ? [...tools]
    : tools.filter((tool) =>
        `${tool.displayName} ${tool.name} ${tool.description}`
          .toLowerCase()
          .includes(normalizedSearch),
      );
}

export { AgentRelationshipsSection };
