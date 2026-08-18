import { Ellipsis, Eye, Gauge, Search } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import {
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";

import { useRootStore } from "@/app/use-root-store";
import {
  AppliedFilterBar,
  CollectionToolbar,
  FilterControl,
  SortControl,
} from "@/components/filters";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AgentRunDetailsDrawer } from "@/features/operations/AgentRunDetailsDrawer";
import {
  formatOperationDate,
  formatOperationEnum,
} from "@/features/operations/operation-formatters";
import {
  AGENT_RUN_FILTER_SCHEMA,
  AGENT_RUN_SORT_OPTIONS,
} from "@/features/operations/operations-list-controls";
import {
  applyAgentRunQuery,
  buildAgentRunSearchParams,
  DEFAULT_AGENT_RUN_QUERY,
  hasFilters,
  parseAgentRunQuery,
} from "@/features/operations/operations.query";
import type {
  AgentRun,
  AgentRunCollectionQuery,
  AgentRunSortField,
  ExecutionBudgetInput,
} from "@/features/operations/operations.types";

const BUDGET_FIELDS = [
  ["max_concurrent_runs", "Concurrent runs", "Maximum active durable runs."],
  [
    "max_active_tokens",
    "Active token capacity",
    "Token capacity shared by active runs.",
  ],
  [
    "max_active_milliseconds",
    "Active time capacity (ms)",
    "Runtime capacity shared by active runs.",
  ],
  [
    "max_active_cost_microunits",
    "Active cost capacity",
    "Cost capacity shared by active runs.",
  ],
  [
    "run_token_limit",
    "Tokens per run",
    "A single run is rejected beyond this amount.",
  ],
  [
    "run_time_limit_milliseconds",
    "Time per run (ms)",
    "A single run is rejected beyond this duration.",
  ],
  [
    "run_cost_limit_microunits",
    "Cost per run",
    "A single run is rejected beyond this amount.",
  ],
  [
    "cost_microunits_per_million_tokens",
    "Cost per million tokens",
    "Organization-defined accounting rate, not a provider invoice price.",
  ],
] as const satisfies readonly (readonly [
  keyof ExecutionBudgetInput,
  string,
  string,
])[];

const AgentRunsPage = observer(function AgentRunsPage() {
  const { operations } = useRootStore();
  const runs = operations.agentRuns;
  const { organizationId, runId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [budgetOpen, setBudgetOpen] = useState(false);
  const searchKey = searchParams.toString();
  const query = useMemo(
    () => parseAgentRunQuery(new URLSearchParams(searchKey)),
    [searchKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);
  const visible = useMemo(
    () => applyAgentRunQuery(runs.items, query, AGENT_RUN_FILTER_SCHEMA),
    [query, runs.items],
  );

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId !== undefined) {
      void runs.loadCollection(organizationId);
      void operations.loadAgentReferences(organizationId);
    }
  }, [operations, organizationId, runs]);
  useEffect(() => {
    if (organizationId !== undefined && runId !== undefined)
      void runs.loadSelected(organizationId, runId);
    else runs.clearSelected();
    return runs.clearSelected;
  }, [organizationId, runId, runs]);

  if (organizationId === undefined) return null;
  const activeOrganizationId = organizationId;
  function setQuery(next: AgentRunCollectionQuery): void {
    setSearchParams(buildAgentRunSearchParams(next));
  }
  function updateQuery(patch: Partial<AgentRunCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }
  function open(id: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/agent-runs/${id}`,
      search: location.search,
    });
  }
  function close(): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/agent-runs`,
      search: location.search,
    });
  }
  function sortBy(field: AgentRunSortField): void {
    updateQuery({
      direction:
        query.sortBy === field
          ? query.direction === "asc"
            ? "desc"
            : "asc"
          : field === "goal"
            ? "asc"
            : "desc",
      sortBy: field,
    });
  }

  return (
    <section
      className="space-y-6 p-4 sm:p-6"
      aria-labelledby="agent-runs-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="agent-runs-title"
            className="text-2xl font-semibold tracking-tight"
          >
            Agent runs
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Inspect durable goals, workflow steps, budget consumption, failures,
            and Agent requests waiting for member input.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            setBudgetOpen(true);
            void runs.loadBudget(activeOrganizationId);
          }}
        >
          <Gauge aria-hidden="true" />
          Execution budget
        </Button>
      </header>
      <CollectionToolbar
        listLabel="Agent runs"
        search={
          <form
            className="relative w-full sm:max-w-sm"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              updateQuery({ search: searchDraft.trim().slice(0, 100) });
            }}
          >
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              className="pr-20 pl-9"
              aria-label="Search Agent runs"
              maxLength={100}
              placeholder="Search goals or IDs"
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
            />
            <Button
              className="absolute top-0 right-0 rounded-l-none"
              variant="ghost"
              type="submit"
            >
              Search
            </Button>
          </form>
        }
        filter={
          <FilterControl
            filterTree={query.filters}
            listLabel="Agent runs"
            schema={AGENT_RUN_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Agent runs"
            options={AGENT_RUN_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) => updateQuery({ direction })}
            onSortChange={sortBy}
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Agent runs"
            schema={AGENT_RUN_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
      />
      <AgentRunsTable
        errorMessage={runs.collectionErrorMessage}
        isLoading={runs.isCollectionLoading}
        items={visible}
        hasActiveFilters={hasFilters(query)}
        agentName={operations.agentName}
        onClear={() =>
          setQuery({
            ...query,
            filters: DEFAULT_AGENT_RUN_QUERY.filters,
            search: "",
          })
        }
        onRetry={() => void runs.loadCollection(activeOrganizationId)}
        onView={open}
      />
      <AgentRunDetailsDrawer
        organizationId={activeOrganizationId}
        runId={runId}
        onClose={close}
      />
      <ExecutionBudgetDialog
        open={budgetOpen}
        organizationId={activeOrganizationId}
        onOpenChange={setBudgetOpen}
      />
    </section>
  );
});

function AgentRunsTable({
  agentName,
  errorMessage,
  hasActiveFilters,
  isLoading,
  items,
  onClear,
  onRetry,
  onView,
}: {
  agentName: (id: string) => string;
  errorMessage: string | null;
  hasActiveFilters: boolean;
  isLoading: boolean;
  items: readonly AgentRun[];
  onClear: () => void;
  onRetry: () => void;
  onView: (id: string) => void;
}) {
  if (errorMessage !== null)
    return (
      <Empty
        title="Agent runs are unavailable"
        description={errorMessage}
        action="Try again"
        onAction={onRetry}
      />
    );
  if (!isLoading && items.length === 0)
    return (
      <Empty
        title={
          hasActiveFilters
            ? "No Agent runs match these filters"
            : "No Agent runs yet"
        }
        description={
          hasActiveFilters
            ? "Change or clear the filters to inspect other runs."
            : "Durable work appears here after a message, schedule, or objective starts an Agent run."
        }
        action={hasActiveFilters ? "Clear filters" : undefined}
        onAction={onClear}
      />
    );
  return (
    <div className="border">
      <div className="divide-y sm:hidden" role="list" aria-label="Agent runs">
        {isLoading
          ? Array.from({ length: 5 }, (_, index) => (
              <RunLoadingCard key={index} />
            ))
          : items.map((run) => (
              <RunCard
                key={run.id}
                run={run}
                agentName={agentName(run.agent_id)}
                onView={onView}
              />
            ))}
      </div>
      <Table className="hidden table-fixed sm:table" aria-label="Agent runs">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[34%]">Goal</TableHead>
            <TableHead className="w-36">State</TableHead>
            <TableHead className="hidden w-40 md:table-cell">Agent</TableHead>
            <TableHead className="hidden w-36 lg:table-cell">Origin</TableHead>
            <TableHead className="w-44">Created</TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <RunLoadingRow key={index} />
              ))
            : items.map((run) => (
                <RunRow
                  key={run.id}
                  run={run}
                  agentName={agentName(run.agent_id)}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>
      <div className="border-t px-3 py-3 text-xs text-muted-foreground">
        {isLoading
          ? "Loading Agent runs…"
          : `${items.length} run${items.length === 1 ? "" : "s"} · most recent 100`}
      </div>
    </div>
  );
}

function RunRow({
  agentName,
  onView,
  run,
}: {
  agentName: string;
  onView: (id: string) => void;
  run: AgentRun;
}) {
  const created = formatOperationDate(run.created_at);
  return (
    <TableRow>
      <TableCell className="whitespace-normal">
        <button
          className="line-clamp-2 text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(run.id)}
        >
          {run.goal}
        </button>
        <p className="mt-0.5 text-xs text-muted-foreground">
          …{run.id.slice(-12)}
        </p>
      </TableCell>
      <TableCell>
        <Badge variant="outline">{formatOperationEnum(run.lifecycle)}</Badge>
        {run.outcome === null ? null : (
          <p className="mt-1 text-xs text-muted-foreground">
            {formatOperationEnum(run.outcome)}
          </p>
        )}
      </TableCell>
      <TableCell className="hidden whitespace-normal md:table-cell">
        {agentName}
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Badge variant="outline">{formatOperationEnum(run.origin_kind)}</Badge>
      </TableCell>
      <TableCell className="whitespace-normal">
        <time dateTime={run.created_at} title={created.title}>
          {created.label}
        </time>
      </TableCell>
      <TableCell className="text-right">
        <RunMenu id={run.id} label={run.goal} onView={onView} />
      </TableCell>
    </TableRow>
  );
}
function RunCard({
  agentName,
  onView,
  run,
}: {
  agentName: string;
  onView: (id: string) => void;
  run: AgentRun;
}) {
  const created = formatOperationDate(run.created_at);
  return (
    <article className="space-y-3 p-4" role="listitem">
      <div className="flex items-start justify-between gap-3">
        <button
          className="line-clamp-3 text-left font-medium underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(run.id)}
        >
          {run.goal}
        </button>
        <RunMenu id={run.id} label={run.goal} onView={onView} />
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">{formatOperationEnum(run.lifecycle)}</Badge>
        <Badge variant="outline">{formatOperationEnum(run.origin_kind)}</Badge>
      </div>
      <p className="text-xs text-muted-foreground">
        {agentName} · {created.label}
      </p>
    </article>
  );
}
function RunMenu({
  id,
  label,
  onView,
}: {
  id: string;
  label: string;
  onView: (id: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for ${label}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onView(id)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
function RunLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-full" />
        <Skeleton className="mt-2 h-3 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-24" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}
function RunLoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-5 w-32" />
      <Skeleton className="h-3 w-40" />
    </div>
  );
}
function Empty({
  action,
  description,
  onAction,
  title,
}: {
  action?: string;
  description: string;
  onAction: () => void;
  title: string;
}) {
  return (
    <div className="border py-16 text-center">
      <p className="text-sm font-medium">{title}</p>
      <p className="mx-auto mt-1 max-w-lg text-sm text-muted-foreground">
        {description}
      </p>
      {action === undefined ? null : (
        <Button className="mt-4" variant="outline" onClick={onAction}>
          {action}
        </Button>
      )}
    </div>
  );
}

const ExecutionBudgetDialog = observer(function ExecutionBudgetDialog({
  open,
  organizationId,
  onOpenChange,
}: {
  open: boolean;
  organizationId: string;
  onOpenChange: (open: boolean) => void;
}) {
  const { operations } = useRootStore();
  const runs = operations.agentRuns;
  const [values, setValues] = useState<Record<string, string>>({});
  const [localError, setLocalError] = useState<string | null>(null);
  useEffect(() => {
    if (!open) return;
    const budget = runs.budget;
    setValues(
      Object.fromEntries(
        BUDGET_FIELDS.map(([key]) => [
          key,
          budget === null ? "" : String(budget[key]),
        ]),
      ),
    );
  }, [open, runs.budget]);
  async function save(): Promise<void> {
    const parsed: Record<string, number> = {};
    for (const [key, label] of BUDGET_FIELDS) {
      const value = Number(values[key]);
      if (!Number.isSafeInteger(value) || value <= 0) {
        setLocalError(`${label} must be a positive whole number.`);
        return;
      }
      parsed[key] = value;
    }
    const input = {
      ...parsed,
      expected_state_revision: runs.budget?.state_revision ?? null,
    } as ExecutionBudgetInput;
    if (await runs.saveBudget(organizationId, input)) onOpenChange(false);
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!runs.isActing) onOpenChange(next);
      }}
    >
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader className="pr-8">
          <DialogTitle>Organization execution budget</DialogTitle>
          <DialogDescription>
            No platform defaults are supplied. Configure concurrency, token,
            time, and cost boundaries explicitly; runs reject rather than
            truncate.
          </DialogDescription>
        </DialogHeader>
        {runs.isBudgetLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 6 }, (_, index) => (
              <Skeleton key={index} className="h-12 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2">
            {BUDGET_FIELDS.map(([key, label, help]) => (
              <div className="space-y-2" key={key}>
                <Label htmlFor={`budget-${key}`}>{label}</Label>
                <Input
                  id={`budget-${key}`}
                  inputMode="numeric"
                  min={1}
                  type="number"
                  value={values[key] ?? ""}
                  onChange={(event) => {
                    setValues((current) => ({
                      ...current,
                      [key]: event.target.value,
                    }));
                    setLocalError(null);
                  }}
                />
                <p className="text-xs leading-5 text-muted-foreground">
                  {help}
                </p>
              </div>
            ))}
          </div>
        )}
        {localError !== null || runs.budgetErrorMessage !== null ? (
          <p className="text-sm text-destructive" role="alert">
            {localError ?? runs.budgetErrorMessage}
          </p>
        ) : null}
        <DialogFooter>
          <Button
            variant="outline"
            disabled={runs.isActing}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            disabled={runs.isActing || runs.isBudgetLoading}
            onClick={() => void save()}
          >
            {runs.isActing
              ? "Saving…"
              : runs.budget === null
                ? "Set budget"
                : "Update budget"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
});

export { AgentRunsPage };
