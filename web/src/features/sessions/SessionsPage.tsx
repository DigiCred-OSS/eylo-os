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
import {
  SESSION_FILTER_SCHEMA,
  SESSION_SORT_OPTIONS,
} from "@/features/sessions/session-list-controls";
import {
  buildSessionCollectionSearchParams,
  DEFAULT_SESSION_QUERY,
  parseSessionCollectionQuery,
} from "@/features/sessions/sessions.query";
import { SessionsTable } from "@/features/sessions/SessionsTable";
import type {
  SessionCollectionQuery,
  UserSessionSortField,
} from "@/features/sessions/sessions.types";

const SessionsPage = observer(function SessionsPage() {
  const { sessions } = useRootStore();
  const { organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const searchParamsKey = searchParams.toString();
  const query = useMemo(
    () => parseSessionCollectionQuery(new URLSearchParams(searchParamsKey)),
    [searchParamsKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);

  useEffect(() => {
    setSearchDraft(query.search);
  }, [query.search]);

  useEffect(() => {
    if (organizationId !== undefined) {
      void sessions.loadCollection(organizationId, query);
    }
  }, [organizationId, query, sessions]);

  if (organizationId === undefined) {
    return null;
  }

  function setQuery(next: SessionCollectionQuery): void {
    setSearchParams(buildSessionCollectionSearchParams(next));
  }

  function updateQuery(patch: Partial<SessionCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }

  function sortBy(field: UserSessionSortField): void {
    const direction =
      query.sortBy === field
        ? query.direction === "asc"
          ? "desc"
          : "asc"
        : field === "contact" || field === "state"
          ? "asc"
          : "desc";
    updateQuery({ direction, page: 1, sortBy: field });
  }

  function openSession(userSessionId: string): void {
    void navigate({
      pathname: `/org/${organizationId}/sessions/${userSessionId}`,
      search: location.search,
    });
  }

  return (
    <section
      className="min-w-0 space-y-6 p-4 sm:p-6"
      aria-labelledby="sessions-title"
    >
      <header className="space-y-1">
        <h1
          id="sessions-title"
          className="text-2xl font-semibold tracking-tight"
        >
          Sessions
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Follow each end-user visit or call across conversations, Agent work,
          voice, files, tools, and transport activity.
        </p>
      </header>

      <CollectionToolbar
        listLabel="Sessions"
        search={
          <form
            className="relative w-full sm:max-w-md"
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
              aria-label="Search sessions"
              maxLength={100}
              placeholder="Search contact or session ID"
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
            listLabel="Sessions"
            schema={SESSION_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Sessions"
            options={SESSION_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) =>
              updateQuery({ direction, page: 1 })
            }
            onSortChange={(sortBy) =>
              updateQuery({
                direction:
                  sortBy === "contact" || sortBy === "state" ? "asc" : "desc",
                page: 1,
                sortBy,
              })
            }
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Sessions"
            schema={SESSION_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
      />

      <SessionsTable
        query={query}
        onClearFilters={() => setQuery(DEFAULT_SESSION_QUERY)}
        onPageChange={(page) => updateQuery({ page })}
        onRetry={() => void sessions.loadCollection(organizationId, query)}
        onSort={sortBy}
        onView={openSession}
      />
    </section>
  );
});

export { SessionsPage };
