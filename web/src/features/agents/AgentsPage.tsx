import { Plus, Search } from "lucide-react";
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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AgentDetailsDrawer } from "@/features/agents/AgentDetailsDrawer";
import { AgentDeleteDialog } from "@/features/agents/AgentDeleteDialog";
import { AgentsTable } from "@/features/agents/AgentsTable";
import {
  AGENT_FILTER_SCHEMA,
  AGENT_SORT_OPTIONS,
} from "@/features/agents/agent-list-controls";
import {
  buildAgentCollectionSearchParams,
  DEFAULT_AGENT_QUERY,
  parseAgentCollectionQuery,
} from "@/features/agents/agents.query";
import type {
  Agent,
  AgentCollectionQuery,
  AgentSortField,
} from "@/features/agents/agents.types";
import { useAsyncContextGuard } from "@/lib/use-async-context-guard";

const AgentsPage = observer(function AgentsPage() {
  const { agents } = useRootStore();
  const { agentId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [agentToDelete, setAgentToDelete] = useState<Agent | null>(null);
  const searchParamsKey = searchParams.toString();
  const contextKey = `${organizationId ?? "missing"}:${agentId ?? "collection"}:${searchParamsKey}`;
  const isCurrentContext = useAsyncContextGuard(contextKey);
  const query = useMemo(
    () => parseAgentCollectionQuery(new URLSearchParams(searchParamsKey)),
    [searchParamsKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);

  useEffect(() => {
    setSearchDraft(query.search);
  }, [query.search]);

  useEffect(() => {
    if (organizationId !== undefined) {
      void agents.loadCollection(organizationId, query);
    }
  }, [agents, organizationId, query]);

  useEffect(() => {
    if (organizationId !== undefined && agentId !== undefined) {
      void agents.loadAgent(organizationId, agentId);
    } else {
      agents.clearSelectedAgent();
    }

    return agents.clearSelectedAgent;
  }, [agentId, agents, organizationId]);

  if (organizationId === undefined) {
    return null;
  }

  function setQuery(nextQuery: AgentCollectionQuery): void {
    setSearchParams(buildAgentCollectionSearchParams(nextQuery));
  }

  function updateQuery(patch: Partial<AgentCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }

  function openAgent(nextAgentId: string): void {
    void navigate({
      pathname: `/org/${organizationId}/agents/${nextAgentId}`,
      search: location.search,
    });
  }

  function closeAgent(): void {
    void navigate({
      pathname: `/org/${organizationId}/agents`,
      search: location.search,
    });
  }

  function createAgent(): void {
    void navigate({
      pathname: `/org/${organizationId}/agents/new`,
      search: location.search,
    });
  }

  function editAgent(nextAgentId: string): void {
    void navigate({
      pathname: `/org/${organizationId}/agents/${nextAgentId}/edit`,
      search: location.search,
    });
  }

  function requestDelete(agent: Agent): void {
    agents.clearDeleteError();
    setAgentToDelete(agent);
  }

  async function confirmDelete(): Promise<boolean> {
    if (agentToDelete === null || organizationId === undefined) {
      return false;
    }

    const submittedContextKey = contextKey;
    const deleted = await agents.deleteAgent(organizationId, agentToDelete.id);
    if (!deleted || !isCurrentContext(submittedContextKey)) {
      return false;
    }

    setAgentToDelete(null);
    if (agents.items.length === 1 && query.page > 1) {
      updateQuery({ page: query.page - 1 });
    } else {
      await agents.loadCollection(organizationId, query);
    }
    return true;
  }

  function sortBy(field: AgentSortField): void {
    const direction =
      query.sortBy === field
        ? query.direction === "asc"
          ? "desc"
          : "asc"
        : field.endsWith("_at")
          ? "desc"
          : "asc";
    updateQuery({ direction, page: 1, sortBy: field });
  }

  return (
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="agents-title">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="agents-title"
            className="text-2xl font-semibold tracking-tight"
          >
            Agents
          </h1>
          <p className="text-sm leading-6 text-muted-foreground">
            Configure and monitor the Agents owned by your organization.
          </p>
        </div>
        <Button onClick={createAgent}>
          <Plus aria-hidden="true" />
          New Agent
        </Button>
      </header>

      <CollectionToolbar
        listLabel="Agents"
        search={
          <form
            className="relative w-full sm:max-w-sm"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              updateQuery({
                page: 1,
                search: searchDraft.trim().slice(0, 100),
              });
            }}
          >
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              className="pr-20 pl-9"
              aria-label="Search Agents"
              maxLength={100}
              placeholder="Search Agents"
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
            listLabel="Agents"
            schema={AGENT_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Agents"
            options={AGENT_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) =>
              updateQuery({ direction, page: 1 })
            }
            onSortChange={(sortBy) =>
              updateQuery({
                direction: sortBy.endsWith("_at") ? "desc" : "asc",
                page: 1,
                sortBy,
              })
            }
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Agents"
            schema={AGENT_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
      />

      <AgentsTable
        query={query}
        onClearFilters={() =>
          setQuery({
            ...query,
            filters: DEFAULT_AGENT_QUERY.filters,
            page: 1,
            search: "",
          })
        }
        onDelete={requestDelete}
        onPageChange={(page) => updateQuery({ page })}
        onRetry={() => void agents.loadCollection(organizationId, query)}
        onSort={sortBy}
        onEdit={editAgent}
        onView={openAgent}
      />

      <AgentDetailsDrawer
        agentId={agentId}
        onClose={closeAgent}
        onEdit={editAgent}
      />

      <AgentDeleteDialog
        agent={agentToDelete}
        errorMessage={agents.deleteErrorMessage}
        isDeleting={agents.isDeleting}
        open={agentToDelete !== null}
        onOpenChange={(open) => {
          if (!open) {
            setAgentToDelete(null);
            agents.clearDeleteError();
          }
        }}
        onConfirm={confirmDelete}
      />
    </section>
  );
});

export { AgentsPage };
