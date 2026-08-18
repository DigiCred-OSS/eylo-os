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
import { AutomationDetailsDrawer } from "@/features/automations/AutomationDetailsDrawer";
import { AutomationsTable } from "@/features/automations/AutomationsTable";
import {
  AUTOMATION_FILTER_SCHEMA,
  AUTOMATION_SORT_OPTIONS,
} from "@/features/automations/automations-list-controls";
import {
  applyAutomationsQuery,
  buildAutomationsSearchParams,
  DEFAULT_AUTOMATIONS_QUERY,
  parseAutomationsQuery,
} from "@/features/automations/automations.query";
import type {
  ScheduleCollectionQuery,
  ScheduleSortField,
} from "@/features/automations/automations.types";

const AutomationsPage = observer(function AutomationsPage() {
  const { automations } = useRootStore();
  const { organizationId, scheduleId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const searchKey = searchParams.toString();
  const query = useMemo(
    () => parseAutomationsQuery(new URLSearchParams(searchKey)),
    [searchKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);
  const visibleItems = useMemo(
    () =>
      applyAutomationsQuery(automations.items, query, AUTOMATION_FILTER_SCHEMA),
    [automations.items, query],
  );

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId !== undefined)
      void automations.loadCollection(organizationId);
  }, [automations, organizationId]);
  useEffect(() => {
    if (organizationId !== undefined && scheduleId !== undefined)
      void automations.loadSelected(organizationId, scheduleId);
    else automations.clearSelected();
    return automations.clearSelected;
  }, [automations, organizationId, scheduleId]);

  if (organizationId === undefined) return null;
  const activeOrganizationId = organizationId;

  function setQuery(next: ScheduleCollectionQuery): void {
    setSearchParams(buildAutomationsSearchParams(next));
  }
  function updateQuery(patch: Partial<ScheduleCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }
  function open(id: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/automations/${id}`,
      search: location.search,
    });
  }
  function close(): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/automations`,
      search: location.search,
    });
  }
  function edit(id: string): void {
    void navigate({
      pathname: `/org/${activeOrganizationId}/automations/${id}/edit`,
      search: location.search,
    });
  }
  function sortBy(field: ScheduleSortField): void {
    updateQuery({
      direction:
        query.sortBy === field
          ? query.direction === "asc"
            ? "desc"
            : "asc"
          : field === "name" || field === "next_at"
            ? "asc"
            : "desc",
      sortBy: field,
    });
  }

  return (
    <section
      className="space-y-6 p-4 sm:p-6"
      aria-labelledby="automations-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <h1
            id="automations-title"
            className="text-2xl font-semibold tracking-tight"
          >
            Automations
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
            Trigger published Agents on one-time or recurring schedules. The
            scheduler only starts the Agent; the Agent decides how to fulfill
            the goal.
          </p>
        </div>
        <Button
          onClick={() =>
            void navigate(`/org/${activeOrganizationId}/automations/new`)
          }
        >
          <Plus aria-hidden="true" />
          New automation
        </Button>
      </header>
      <CollectionToolbar
        listLabel="Automations"
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
              aria-label="Search automations"
              maxLength={100}
              placeholder="Search automations"
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
            listLabel="Automations"
            schema={AUTOMATION_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Automations"
            options={AUTOMATION_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) => updateQuery({ direction })}
            onSortChange={sortBy}
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Automations"
            schema={AUTOMATION_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters })}
          />
        }
      />
      <AutomationsTable
        errorMessage={automations.collectionErrorMessage}
        isLoading={automations.isCollectionLoading}
        items={visibleItems}
        query={query}
        onClearFilters={() =>
          setQuery({
            ...query,
            filters: DEFAULT_AUTOMATIONS_QUERY.filters,
            search: "",
          })
        }
        onEdit={edit}
        onRetry={() => void automations.loadCollection(activeOrganizationId)}
        onView={open}
      />
      <AutomationDetailsDrawer
        organizationId={activeOrganizationId}
        scheduleId={scheduleId}
        onClose={close}
        onEdit={edit}
      />
    </section>
  );
});

export { AutomationsPage };
