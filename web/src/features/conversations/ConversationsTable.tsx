import { ArrowDown, ArrowUp, ArrowUpDown, Ellipsis, Eye } from "lucide-react";
import { observer } from "mobx-react-lite";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  formatConversationContact,
  formatConversationDate,
  formatConversationEnum,
} from "@/features/conversations/conversation-formatters";
import { hasConversationCollectionFilters } from "@/features/conversations/conversations.query";
import type {
  ConversationCollectionQuery,
  ConversationListItem,
  ConversationSortField,
} from "@/features/conversations/conversations.types";

interface ConversationsTableProps {
  onClearFilters: () => void;
  onPageChange: (page: number) => void;
  onRetry: () => void;
  onSort: (field: ConversationSortField) => void;
  onView: (conversationId: string) => void;
  query: ConversationCollectionQuery;
}

const ConversationsTable = observer(function ConversationsTable({
  onClearFilters,
  onPageChange,
  onRetry,
  onSort,
  onView,
  query,
}: ConversationsTableProps) {
  const { conversations } = useRootStore();

  if (conversations.collectionErrorMessage !== null) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Conversations are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {conversations.collectionErrorMessage}
        </p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  const hasFilters = hasConversationCollectionFilters(query);
  if (!conversations.isCollectionLoading && conversations.items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters
            ? "No conversations match these filters"
            : "No conversations yet"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to inspect other conversations."
            : "Conversations appear after a user or scheduled trigger starts an Agent."}
        </p>
        {hasFilters ? (
          <Button className="mt-4" variant="outline" onClick={onClearFilters}>
            Clear filters
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="border">
      <div
        className="divide-y sm:hidden"
        role="list"
        aria-label="Conversations"
      >
        {conversations.isCollectionLoading
          ? Array.from({ length: 5 }, (_, index) => (
              <ConversationLoadingCard key={index} />
            ))
          : conversations.items.map((item) => (
              <ConversationCard
                key={item.conversation.id}
                item={item}
                onView={onView}
              />
            ))}
      </div>

      <Table className="hidden table-fixed sm:table" aria-label="Conversations">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortableHead
              className="w-[32%]"
              field="title"
              label="Conversation"
              query={query}
              onSort={onSort}
            />
            <TableHead className="hidden w-[16%] lg:table-cell">
              Agent
            </TableHead>
            <TableHead className="w-28">Status</TableHead>
            <TableHead className="w-24">Channel</TableHead>
            <TableHead className="hidden w-20 md:table-cell">
              Messages
            </TableHead>
            <SortableHead
              className="hidden w-40 xl:table-cell"
              field="updated_at"
              label="Updated"
              query={query}
              onSort={onSort}
            />
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {conversations.isCollectionLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <ConversationLoadingRow key={index} />
              ))
            : conversations.items.map((item) => (
                <ConversationRow
                  key={item.conversation.id}
                  item={item}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>

      <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-t px-3 py-2">
        <p className="text-xs text-muted-foreground">
          {paginationLabel(
            conversations.page,
            conversations.limit,
            conversations.items.length,
            conversations.total,
          )}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={
              conversations.isCollectionLoading || conversations.page <= 1
            }
            onClick={() => onPageChange(conversations.page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={
              conversations.isCollectionLoading || !conversations.hasMore
            }
            onClick={() => onPageChange(conversations.page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
});

function ConversationRow({
  item,
  onView,
}: {
  item: ConversationListItem;
  onView: (conversationId: string) => void;
}) {
  const { aggregate, conversation } = item;
  const title = conversation.title?.trim() || "Untitled conversation";
  return (
    <TableRow>
      <TableCell className="min-w-0 whitespace-normal">
        <button
          className="block max-w-full break-words text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(conversation.id)}
        >
          {title}
        </button>
        <p className="mt-0.5 break-words text-xs text-muted-foreground">
          {formatConversationContact(item.aggregate?.contact)}
        </p>
      </TableCell>
      <TableCell className="hidden min-w-0 whitespace-normal lg:table-cell">
        <p className="break-words text-sm">
          {aggregate?.primaryAgent?.name ?? "No Agent resolved"}
        </p>
      </TableCell>
      <TableCell>
        <Badge
          variant={conversation.status === "ACTIVE" ? "default" : "outline"}
        >
          {formatConversationEnum(conversation.status)}
        </Badge>
      </TableCell>
      <TableCell className="whitespace-normal">
        <Badge variant="outline">
          {formatConversationEnum(conversation.channel)}
        </Badge>
      </TableCell>
      <TableCell className="hidden text-muted-foreground md:table-cell">
        {aggregate?.messageCount ?? "—"}
      </TableCell>
      <TableCell className="hidden whitespace-normal text-muted-foreground xl:table-cell">
        <DateValue value={conversation.updatedAt} />
      </TableCell>
      <TableCell className="text-right">
        <ConversationActions
          id={conversation.id}
          title={title}
          onView={onView}
        />
      </TableCell>
    </TableRow>
  );
}

function ConversationCard({
  item,
  onView,
}: {
  item: ConversationListItem;
  onView: (conversationId: string) => void;
}) {
  const title = item.conversation.title?.trim() || "Untitled conversation";
  return (
    <article
      className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-3 p-4"
      role="listitem"
    >
      <button
        className="min-w-0 text-left focus-visible:rounded-sm focus-visible:outline-2"
        type="button"
        onClick={() => onView(item.conversation.id)}
      >
        <span className="block break-words text-sm font-medium">{title}</span>
        <span className="mt-1 block break-words text-xs text-muted-foreground">
          {item.aggregate?.primaryAgent?.name ?? "No Agent resolved"} ·{" "}
          {formatConversationContact(item.aggregate?.contact)}
        </span>
        <span className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <span>Status</span>
            <Badge variant="outline">
              {formatConversationEnum(item.conversation.status)}
            </Badge>
          </span>
          <span className="inline-flex items-center gap-1">
            <span>Channel</span>
            <Badge variant="outline">
              {formatConversationEnum(item.conversation.channel)}
            </Badge>
          </span>
          <span>{item.aggregate?.messageCount ?? "—"} messages</span>
          <span>
            Updated {formatConversationDate(item.conversation.updatedAt).label}
          </span>
        </span>
      </button>
      <ConversationActions
        id={item.conversation.id}
        title={title}
        onView={onView}
      />
    </article>
  );
}

function ConversationActions({
  id,
  onView,
  title,
}: {
  id: string;
  onView: (conversationId: string) => void;
  title: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for ${title}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-36">
        <DropdownMenuItem onClick={() => onView(id)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SortableHead({
  className,
  field,
  label,
  onSort,
  query,
}: {
  className?: string;
  field: ConversationSortField;
  label: string;
  onSort: (field: ConversationSortField) => void;
  query: ConversationCollectionQuery;
}) {
  const active = query.sortBy === field;
  const Icon = !active
    ? ArrowUpDown
    : query.direction === "asc"
      ? ArrowUp
      : ArrowDown;
  return (
    <TableHead
      className={className}
      aria-sort={
        active
          ? query.direction === "asc"
            ? "ascending"
            : "descending"
          : "none"
      }
    >
      <Button
        className="-ml-2 h-8 px-2"
        variant="ghost"
        onClick={() => onSort(field)}
      >
        {label}
        <Icon aria-hidden="true" />
      </Button>
    </TableHead>
  );
}

function DateValue({ value }: { value: string | null | undefined }) {
  const formatted = formatConversationDate(value);
  return value == null ? (
    formatted.label
  ) : (
    <time dateTime={value} title={formatted.title}>
      {formatted.label}
    </time>
  );
}

function paginationLabel(
  page: number,
  limit: number,
  count: number,
  total: number,
): string {
  if (total === 0) {
    return "No conversations";
  }
  const start = (page - 1) * limit + 1;
  return `Showing ${start}–${start + count - 1} of ${total} conversations`;
}

function ConversationLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-8 w-4/5" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-5 w-28" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-8 w-20" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-16" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-5 w-10" />
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        <Skeleton className="h-5 w-32" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}

function ConversationLoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-5 w-4/5" />
      <Skeleton className="h-4 w-3/5" />
      <Skeleton className="h-6 w-2/5" />
    </div>
  );
}

export { ConversationsTable };
