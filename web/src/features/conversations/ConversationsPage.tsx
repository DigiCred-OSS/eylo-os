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
  CONVERSATION_FILTER_SCHEMA,
  CONVERSATION_SORT_OPTIONS,
} from "@/features/conversations/conversation-list-controls";
import { ConversationsTable } from "@/features/conversations/ConversationsTable";
import {
  buildConversationCollectionSearchParams,
  DEFAULT_CONVERSATION_QUERY,
  parseConversationCollectionQuery,
} from "@/features/conversations/conversations.query";
import type {
  ConversationCollectionQuery,
  ConversationSortField,
} from "@/features/conversations/conversations.types";

const ConversationsPage = observer(function ConversationsPage() {
  const { conversations } = useRootStore();
  const { organizationId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const searchParamsKey = searchParams.toString();
  const query = useMemo(
    () =>
      parseConversationCollectionQuery(new URLSearchParams(searchParamsKey)),
    [searchParamsKey],
  );
  const [searchDraft, setSearchDraft] = useState(query.search);

  useEffect(() => {
    setSearchDraft(query.search);
  }, [query.search]);

  useEffect(() => {
    if (organizationId !== undefined) {
      void conversations.loadCollection(organizationId, query);
    }
  }, [conversations, organizationId, query]);

  if (organizationId === undefined) {
    return null;
  }

  function setQuery(next: ConversationCollectionQuery): void {
    setSearchParams(buildConversationCollectionSearchParams(next));
  }

  function updateQuery(patch: Partial<ConversationCollectionQuery>): void {
    setQuery({ ...query, ...patch });
  }

  function sortBy(field: ConversationSortField): void {
    const direction =
      query.sortBy === field
        ? query.direction === "asc"
          ? "desc"
          : "asc"
        : field === "title"
          ? "asc"
          : "desc";
    updateQuery({ direction, page: 1, sortBy: field });
  }

  function openConversation(conversationId: string): void {
    void navigate({
      pathname: `/org/${organizationId}/conversations/${conversationId}`,
      search: location.search,
    });
  }

  return (
    <section
      className="min-w-0 space-y-6 p-4 sm:p-6"
      aria-labelledby="conversations-title"
    >
      <header className="space-y-1">
        <h1
          id="conversations-title"
          className="text-2xl font-semibold tracking-tight"
        >
          Conversations
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Review Agent interactions, tool exchanges, handoffs, and available
          voice recordings.
        </p>
      </header>

      <CollectionToolbar
        listLabel="Conversations"
        search={
          <form
            className="relative w-full sm:max-w-md"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              updateQuery({
                page: 1,
                search: searchDraft.trim().slice(0, 200),
              });
            }}
          >
            <Search
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              className="pr-20 pl-9"
              aria-label="Search conversations"
              maxLength={200}
              placeholder="Search conversation titles"
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
            listLabel="Conversations"
            schema={CONVERSATION_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
        sort={
          <SortControl
            direction={query.direction}
            listLabel="Conversations"
            options={CONVERSATION_SORT_OPTIONS}
            sort={query.sortBy}
            onDirectionChange={(direction) =>
              updateQuery({ direction, page: 1 })
            }
            onSortChange={(sortBy) =>
              updateQuery({
                direction: sortBy === "title" ? "asc" : "desc",
                page: 1,
                sortBy,
              })
            }
          />
        }
        appliedFilters={
          <AppliedFilterBar
            filterTree={query.filters}
            listLabel="Conversations"
            schema={CONVERSATION_FILTER_SCHEMA}
            onChange={(filters) => updateQuery({ filters, page: 1 })}
          />
        }
      />

      <ConversationsTable
        query={query}
        onClearFilters={() => setQuery(DEFAULT_CONVERSATION_QUERY)}
        onPageChange={(page) => updateQuery({ page })}
        onRetry={() => void conversations.loadCollection(organizationId, query)}
        onSort={sortBy}
        onView={openConversation}
      />
    </section>
  );
});

export { ConversationsPage };
