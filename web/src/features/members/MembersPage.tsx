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
import { MemberDetailsDrawer } from "@/features/members/MemberDetailsDrawer";
import { MembersTable } from "@/features/members/MembersTable";
import {
  MEMBER_FILTER_SCHEMA,
  MEMBER_SORT_OPTIONS,
} from "@/features/members/member-list-controls";
import {
  buildMemberCollectionSearchParams,
  DEFAULT_MEMBER_QUERY,
  parseMemberCollectionQuery,
} from "@/features/members/members.query";
import type {
  MemberCollectionQuery,
  MemberSortField,
} from "@/features/members/members.types";

const MembersPage = observer(function MembersPage() {
  const { members } = useRootStore();
  const { memberId, organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const key = searchParams.toString();
  const query = useMemo(
    () => parseMemberCollectionQuery(new URLSearchParams(key)),
    [key],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);

  useEffect(() => setSearchDraft(query.search), [query.search]);
  useEffect(() => {
    if (organizationId !== undefined)
      void members.loadCollection(organizationId, query);
  }, [members, organizationId, query]);
  useEffect(() => {
    if (organizationId !== undefined && memberId !== undefined)
      void members.loadSelected(organizationId, memberId);
    else members.clearSelected();
    return members.clearSelected;
  }, [memberId, members, organizationId]);

  if (organizationId === undefined) return null;
  const basePath = `/org/${organizationId}/members`;
  const setQuery = (next: MemberCollectionQuery) =>
    setSearchParams(buildMemberCollectionSearchParams(next));
  const updateQuery = (patch: Partial<MemberCollectionQuery>) =>
    setQuery({ ...query, ...patch });
  const sortBy = (field: MemberSortField) =>
    updateQuery({
      direction:
        query.sortBy === field
          ? query.direction === "asc"
            ? "desc"
            : "asc"
          : field.endsWith("_at") || field === "last_login"
            ? "desc"
            : "asc",
      page: 1,
      sortBy: field,
    });

  return (
    <section className="space-y-6 p-4 sm:p-6" aria-labelledby="members-title">
      <header className="space-y-1">
        <h1
          id="members-title"
          className="text-2xl font-semibold tracking-tight"
        >
          Members
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Review the people who can access this organization. Membership changes
          are managed outside this console surface.
        </p>
      </header>
      <CollectionToolbar
        listLabel="Members"
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
              aria-label="Search members"
              maxLength={100}
              placeholder="Search name or email"
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
            listLabel="Members"
            schema={MEMBER_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Members"
            options={MEMBER_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) =>
              updateQuery({ direction, page: 1 })
            }
            onSortChange={(sortBy) =>
              updateQuery({
                direction:
                  sortBy.endsWith("_at") || sortBy === "last_login"
                    ? "desc"
                    : "asc",
                page: 1,
                sortBy,
              })
            }
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Members"
            schema={MEMBER_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
      />
      <MembersTable
        query={query}
        onClearFilters={() => setQuery(DEFAULT_MEMBER_QUERY)}
        onPageChange={(page) => updateQuery({ page })}
        onRetry={() => void members.loadCollection(organizationId, query)}
        onSort={sortBy}
        onView={(id) =>
          void navigate({
            pathname: `${basePath}/${id}`,
            search: location.search,
          })
        }
      />
      <MemberDetailsDrawer
        memberId={memberId}
        onClose={() =>
          void navigate({ pathname: basePath, search: location.search })
        }
      />
    </section>
  );
});

export { MembersPage };
