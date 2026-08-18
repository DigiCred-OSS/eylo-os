import { Search } from "lucide-react";
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
import { MemoryDetailsDrawer } from "@/features/memory/MemoryDetailsDrawer";
import { MemoryTable } from "@/features/memory/MemoryTable";
import {
  MEMORY_FILTER_SCHEMA,
  MEMORY_SORT_OPTIONS,
} from "@/features/memory/memory-list-controls";
import {
  buildMemoryCollectionSearchParams,
  DEFAULT_MEMORY_QUERY,
  parseMemoryCollectionQuery,
  toMemoryListRequest,
} from "@/features/memory/memory.query";
import type { MemoryCollectionQuery } from "@/features/memory/memory.types";

const MemoryPage = observer(function MemoryPage() {
  const { memory } = useRootStore();
  const { memoryId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const searchParamsKey = searchParams.toString();
  const query = useMemo(
    () => parseMemoryCollectionQuery(new URLSearchParams(searchParamsKey)),
    [searchParamsKey],
  );
  const request = useMemo(() => toMemoryListRequest(query, 0), [query]);
  const [searchDraft, setSearchDraft] = useState(query.search);

  useEffect(() => {
    setSearchDraft(query.search);
  }, [query.search]);

  useEffect(() => {
    if (organizationId !== undefined) {
      void memory.loadCollection(organizationId, request);
    }
  }, [memory, organizationId, request]);

  useEffect(() => {
    if (organizationId !== undefined && memoryId !== undefined) {
      void memory.loadSelected(organizationId, memoryId);
    } else {
      memory.clearSelected();
    }
    return memory.clearSelected;
  }, [memory, memoryId, organizationId]);

  if (organizationId === undefined) {
    return null;
  }
  const activeOrganizationId = organizationId;

  function setQuery(next: MemoryCollectionQuery): void {
    setSearchParams(buildMemoryCollectionSearchParams(next));
  }

  function updateQuery(patch: Partial<MemoryCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }

  function openMemory(nextMemoryId: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/memory/${nextMemoryId}`,
      search: location.search,
    });
  }

  function closeMemory(): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/memory`,
      search: location.search,
    });
  }

  return (
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="memory-title">
      <header className="space-y-1">
        <h1 id="memory-title" className="text-2xl font-semibold tracking-tight">
          Memory
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Inspect what Agents saved, what they recalled, and what has expired
          across Agent, User, and Conversation memory.
        </p>
      </header>

      {memory.isCollectionStale ? (
        <div
          className="border border-warning/40 bg-warning/10 p-3 text-sm"
          role="alert"
        >
          Showing the last loaded memories. {memory.collectionErrorMessage}
        </div>
      ) : null}

      <CollectionToolbar
        listLabel="Memories"
        search={
          <form
            className="relative w-full sm:max-w-md"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              updateQuery({ search: searchDraft.trim().slice(0, 200) });
            }}
          >
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              className="pr-20 pl-9"
              aria-label="Search memories"
              maxLength={200}
              placeholder="Search remembered facts"
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
            listLabel="Memories"
            schema={MEMORY_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Memories"
            options={MEMORY_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) => updateQuery({ direction })}
            onSortChange={(sortBy) =>
              updateQuery({ direction: "desc", sortBy })
            }
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Memories"
            schema={MEMORY_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
      />

      <MemoryTable
        query={query}
        onClearFilters={() => setQuery(DEFAULT_MEMORY_QUERY)}
        onLoadMore={() => void memory.loadMore(activeOrganizationId)}
        onRetry={() =>
          void memory.loadCollection(activeOrganizationId, request)
        }
        onView={openMemory}
      />

      <MemoryDetailsDrawer memoryId={memoryId} onClose={closeMemory} />
    </section>
  );
});

export { MemoryPage };
