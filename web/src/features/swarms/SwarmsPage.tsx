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
import { SwarmDeleteDialog } from "@/features/swarms/SwarmDeleteDialog";
import { SwarmDetailsDrawer } from "@/features/swarms/SwarmDetailsDrawer";
import {
  SWARM_FILTER_SCHEMA,
  SWARM_SORT_OPTIONS,
} from "@/features/swarms/swarm-list-controls";
import {
  buildSwarmCollectionSearchParams,
  DEFAULT_SWARM_QUERY,
  parseSwarmCollectionQuery,
} from "@/features/swarms/swarms.query";
import type {
  Swarm,
  SwarmCollectionQuery,
  SwarmSortField,
} from "@/features/swarms/swarms.types";
import { SwarmsTable } from "@/features/swarms/SwarmsTable";

const SwarmsPage = observer(function SwarmsPage() {
  const { swarms } = useRootStore();
  const { organizationId, swarmId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [swarmToDelete, setSwarmToDelete] = useState<Swarm | null>(null);
  const searchParamsKey = searchParams.toString();
  const query = useMemo(
    () => parseSwarmCollectionQuery(new URLSearchParams(searchParamsKey)),
    [searchParamsKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId !== undefined)
      void swarms.loadCollection(organizationId, query);
  }, [organizationId, query, swarms]);
  useEffect(() => {
    if (organizationId !== undefined && swarmId !== undefined)
      void swarms.loadSelected(organizationId, swarmId);
    else swarms.clearSelected();
    return swarms.clearSelected;
  }, [organizationId, swarmId, swarms]);

  if (organizationId === undefined) return null;
  const activeOrganizationId = organizationId;
  const basePath = `/org/${activeOrganizationId}/swarms`;

  function setQuery(next: SwarmCollectionQuery): void {
    setSearchParams(buildSwarmCollectionSearchParams(next));
  }

  function updateQuery(patch: Partial<SwarmCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }

  function openSwarm(nextSwarmId: string): void {
    void navigate({
      pathname: `${basePath}/${nextSwarmId}`,
      search: location.search,
    });
  }

  function editSwarm(nextSwarmId: string): void {
    void navigate({
      pathname: `${basePath}/${nextSwarmId}/edit`,
      search: location.search,
    });
  }

  async function confirmDelete(): Promise<boolean> {
    if (swarmToDelete === null) return false;
    const deleted = await swarms.deleteSwarm(
      activeOrganizationId,
      swarmToDelete.id,
    );
    if (!deleted) return false;
    if (swarmId === swarmToDelete.id) {
      void navigate({ pathname: basePath, search: location.search });
    }
    setSwarmToDelete(null);
    if (swarms.items.length === 0 && query.page > 1) {
      updateQuery({ page: query.page - 1 });
    }
    return true;
  }

  function sortBy(field: SwarmSortField): void {
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
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="swarms-title">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="swarms-title"
            className="text-2xl font-semibold tracking-tight"
          >
            Swarms
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Compose conversational Agents into a versioned topology for
            coordinated work.
          </p>
        </div>
        <Button onClick={() => void navigate(`${basePath}/new`)}>
          <Plus aria-hidden="true" />
          New Swarm
        </Button>
      </header>
      <CollectionToolbar
        listLabel="Swarms"
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
              aria-label="Search Swarms"
              maxLength={100}
              placeholder="Search Swarms"
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
            listLabel="Swarms"
            schema={SWARM_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Swarms"
            options={SWARM_SORT_OPTIONS}
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
            listLabel="Swarms"
            schema={SWARM_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
      />
      <SwarmsTable
        query={query}
        onClearFilters={() =>
          setQuery({
            ...query,
            filters: DEFAULT_SWARM_QUERY.filters,
            page: 1,
            search: "",
          })
        }
        onDelete={(swarm) => {
          swarms.clearDeleteError();
          setSwarmToDelete(swarm);
        }}
        onEdit={editSwarm}
        onPageChange={(page) => updateQuery({ page })}
        onRetry={() => void swarms.loadCollection(activeOrganizationId, query)}
        onSort={sortBy}
        onView={openSwarm}
      />
      <SwarmDetailsDrawer
        swarmId={swarmId}
        onClose={() =>
          void navigate({ pathname: basePath, search: location.search })
        }
        onEdit={editSwarm}
      />
      <SwarmDeleteDialog
        errorMessage={swarms.deleteErrorMessage}
        isDeleting={swarms.isDeleting}
        open={swarmToDelete !== null}
        swarm={swarmToDelete}
        onConfirm={confirmDelete}
        onOpenChange={(open) => {
          if (!open) {
            setSwarmToDelete(null);
            swarms.clearDeleteError();
          }
        }}
      />
    </section>
  );
});

export { SwarmsPage };
