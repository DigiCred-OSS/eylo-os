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
import { KnowledgeDeleteDialog } from "@/features/knowledge/KnowledgeDeleteDialog";
import { KnowledgeDetailsDrawer } from "@/features/knowledge/KnowledgeDetailsDrawer";
import { KnowledgeTable } from "@/features/knowledge/KnowledgeTable";
import {
  KNOWLEDGE_FILTER_SCHEMA,
  KNOWLEDGE_SORT_OPTIONS,
} from "@/features/knowledge/knowledge-list-controls";
import {
  applyKnowledgeCollectionQuery,
  buildKnowledgeCollectionSearchParams,
  DEFAULT_KNOWLEDGE_QUERY,
  parseKnowledgeCollectionQuery,
} from "@/features/knowledge/knowledge.query";
import type {
  Knowledgebase,
  KnowledgeCollectionQuery,
  KnowledgeSortField,
} from "@/features/knowledge/knowledge.types";
import { useAsyncContextGuard } from "@/lib/use-async-context-guard";

const KnowledgePage = observer(function KnowledgePage() {
  const { auth, knowledge } = useRootStore();
  const { knowledgebaseId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [knowledgebaseToDelete, setKnowledgebaseToDelete] =
    useState<Knowledgebase | null>(null);
  const searchParamsKey = searchParams.toString();
  const query = useMemo(
    () => parseKnowledgeCollectionQuery(new URLSearchParams(searchParamsKey)),
    [searchParamsKey],
  );
  const visibleItems = useMemo(
    () =>
      applyKnowledgeCollectionQuery(
        knowledge.items,
        query,
        KNOWLEDGE_FILTER_SCHEMA,
      ),
    [knowledge.items, query],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);
  const contextKey = `${organizationId ?? "missing"}:${knowledgebaseId ?? "collection"}:${searchParamsKey}`;
  const isCurrentContext = useAsyncContextGuard(contextKey);
  const detailView = location.pathname.endsWith("/content")
    ? "content"
    : "overview";

  useEffect(() => {
    setSearchDraft(query.search);
  }, [query.search]);

  useEffect(() => {
    if (organizationId !== undefined) {
      void knowledge.loadCollection(organizationId);
    }
  }, [knowledge, organizationId]);

  useEffect(() => {
    if (organizationId !== undefined && knowledgebaseId !== undefined) {
      void knowledge.loadSelected(organizationId, knowledgebaseId);
    } else {
      knowledge.clearSelected();
    }
    return knowledge.clearSelected;
  }, [knowledge, knowledgebaseId, organizationId]);

  if (organizationId === undefined) {
    return null;
  }
  const activeOrganizationId: string = organizationId;

  function setQuery(nextQuery: KnowledgeCollectionQuery): void {
    setSearchParams(buildKnowledgeCollectionSearchParams(nextQuery));
  }

  function updateQuery(patch: Partial<KnowledgeCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }

  function openKnowledgebase(nextKnowledgebaseId: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/knowledge/${nextKnowledgebaseId}`,
      search: location.search,
    });
  }

  function closeKnowledgebase(): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/knowledge`,
      search: location.search,
    });
  }

  function changeDetailView(view: "content" | "overview"): void {
    if (knowledgebaseId === undefined) {
      return;
    }
    void navigate({
      pathname:
        view === "content"
          ? `/org/${activeOrganizationId}/knowledge/${knowledgebaseId}/content`
          : `/org/${activeOrganizationId}/knowledge/${knowledgebaseId}`,
      search: location.search,
    });
  }

  function createKnowledgebase(): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/knowledge/new`,
      search: location.search,
    });
  }

  function editKnowledgebase(nextKnowledgebaseId: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/knowledge/${nextKnowledgebaseId}/edit`,
      search: location.search,
    });
  }

  function requestDelete(knowledgebase: Knowledgebase): void {
    knowledge.clearDeleteError();
    setKnowledgebaseToDelete(knowledgebase);
  }

  async function confirmDelete(): Promise<boolean> {
    if (knowledgebaseToDelete === null) {
      return false;
    }
    const submittedContextKey = contextKey;
    const deleted = await knowledge.deleteKnowledgebase(
      activeOrganizationId,
      knowledgebaseToDelete.id,
    );
    if (!deleted || !isCurrentContext(submittedContextKey)) {
      return false;
    }
    if (knowledgebaseId === knowledgebaseToDelete.id) {
      closeKnowledgebase();
    }
    setKnowledgebaseToDelete(null);
    return true;
  }

  function sortBy(field: KnowledgeSortField): void {
    const direction =
      query.sortBy === field
        ? query.direction === "asc"
          ? "desc"
          : "asc"
        : field === "updated_at"
          ? "desc"
          : "asc";
    updateQuery({ direction, sortBy: field });
  }

  return (
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="knowledge-title">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="knowledge-title"
            className="text-2xl font-semibold tracking-tight"
          >
            Knowledge
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Configure retrievable content, monitor ingestion, then grant it to
            Agents explicitly.
          </p>
        </div>
        <Button onClick={createKnowledgebase}>
          <Plus aria-hidden="true" />
          New knowledgebase
        </Button>
      </header>

      {knowledge.isCollectionStale ? (
        <div
          className="border border-warning/40 bg-warning/10 p-3 text-sm"
          role="alert"
        >
          Showing the last loaded knowledgebases.{" "}
          {knowledge.collectionErrorMessage}
        </div>
      ) : null}

      <CollectionToolbar
        listLabel="Knowledgebases"
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
              aria-label="Search knowledgebases"
              maxLength={100}
              placeholder="Search knowledgebases"
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
            listLabel="Knowledgebases"
            schema={KNOWLEDGE_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Knowledgebases"
            options={KNOWLEDGE_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) => updateQuery({ direction })}
            onSortChange={(sortBy) =>
              updateQuery({
                direction: sortBy === "updated_at" ? "desc" : "asc",
                sortBy,
              })
            }
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Knowledgebases"
            schema={KNOWLEDGE_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
      />

      <KnowledgeTable
        items={visibleItems}
        query={query}
        onClearFilters={() =>
          setQuery({
            ...query,
            filters: DEFAULT_KNOWLEDGE_QUERY.filters,
            search: "",
          })
        }
        onDelete={requestDelete}
        onEdit={editKnowledgebase}
        onRetry={() => void knowledge.loadCollection(activeOrganizationId)}
        onSort={sortBy}
        onView={openKnowledgebase}
      />

      <KnowledgeDetailsDrawer
        activeView={detailView}
        knowledgebaseId={knowledgebaseId}
        memberKey={auth.member?.email ?? null}
        organizationId={activeOrganizationId}
        returnTo={`${location.pathname}${location.search}`}
        onClose={closeKnowledgebase}
        onEdit={editKnowledgebase}
        onViewChange={changeDetailView}
      />

      <KnowledgeDeleteDialog
        knowledgebase={knowledgebaseToDelete}
        errorMessage={knowledge.deleteErrorMessage}
        isDeleting={knowledge.isDeleting}
        open={knowledgebaseToDelete !== null}
        onOpenChange={(open) => {
          if (!open) {
            setKnowledgebaseToDelete(null);
            knowledge.clearDeleteError();
          }
        }}
        onConfirm={confirmDelete}
      />
    </section>
  );
});

export { KnowledgePage };
