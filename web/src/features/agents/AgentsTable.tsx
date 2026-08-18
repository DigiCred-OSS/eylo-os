import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Ellipsis,
  Eye,
  Pencil,
  Trash2,
} from "lucide-react";
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
import { AgentDateTime } from "@/features/agents/AgentDateTime";
import { AgentStatusBadge } from "@/features/agents/AgentStatusBadge";
import { formatAgentEnum } from "@/features/agents/agent-formatters";
import { hasAgentCollectionFilters } from "@/features/agents/agents.query";
import type {
  Agent,
  AgentCollectionQuery,
  AgentSortField,
} from "@/features/agents/agents.types";

interface AgentsTableProps {
  onClearFilters: () => void;
  onDelete: (agent: Agent) => void;
  onEdit: (agentId: string) => void;
  onPageChange: (page: number) => void;
  onRetry: () => void;
  onSort: (field: AgentSortField) => void;
  onView: (agentId: string) => void;
  query: AgentCollectionQuery;
}

const AgentsTable = observer(function AgentsTable({
  onClearFilters,
  onDelete,
  onEdit,
  onPageChange,
  onRetry,
  onSort,
  onView,
  query,
}: AgentsTableProps) {
  const { agents } = useRootStore();

  if (agents.collectionErrorMessage !== null) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Agents are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {agents.collectionErrorMessage}
        </p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  const hasFilters = hasAgentCollectionFilters(query);

  if (!agents.isCollectionLoading && agents.items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters ? "No Agents match these filters" : "No Agents yet"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to see other Agents."
            : "Create an Agent to start configuring its behavior."}
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
      <Table aria-label="Agents">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortableHead
              field="name"
              label="Name"
              query={query}
              onSort={onSort}
            />
            <TableHead className="hidden min-w-72 lg:table-cell">
              Description
            </TableHead>
            <SortableHead
              className="hidden md:table-cell"
              field="kind"
              label="Kind"
              query={query}
              onSort={onSort}
            />
            <SortableHead
              field="status"
              label="Status"
              query={query}
              onSort={onSort}
            />
            <SortableHead
              className="hidden sm:table-cell"
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
          {agents.isCollectionLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <AgentLoadingRow key={index} />
              ))
            : agents.items.map((agent) => (
                <AgentRow
                  key={agent.id}
                  agent={agent}
                  onDelete={onDelete}
                  onEdit={onEdit}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>

      <div className="flex min-h-14 items-center justify-between gap-4 border-t px-3 py-2">
        <p className="text-xs text-muted-foreground">
          {getPaginationLabel(
            agents.page,
            agents.limit,
            agents.items.length,
            agents.total,
          )}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={agents.isCollectionLoading || agents.page <= 1}
            onClick={() => onPageChange(agents.page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={agents.isCollectionLoading || !agents.hasMore}
            onClick={() => onPageChange(agents.page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
});

function AgentRow({
  agent,
  onDelete,
  onEdit,
  onView,
}: {
  agent: Agent;
  onDelete: (agent: Agent) => void;
  onEdit: (agentId: string) => void;
  onView: (agentId: string) => void;
}) {
  return (
    <TableRow>
      <TableCell className="max-w-64 whitespace-normal">
        <button
          className="text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(agent.id)}
        >
          {agent.name}
        </button>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {agent.slug}
        </p>
      </TableCell>
      <TableCell className="hidden max-w-96 whitespace-normal text-muted-foreground lg:table-cell">
        <p className="line-clamp-2 leading-5">
          {agent.description?.trim() || "No description"}
        </p>
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Badge variant="outline">{formatAgentEnum(agent.kind)}</Badge>
      </TableCell>
      <TableCell>
        <AgentStatusBadge status={agent.status} />
      </TableCell>
      <TableCell className="hidden text-muted-foreground sm:table-cell">
        <AgentDateTime value={agent.updatedAt} />
      </TableCell>
      <TableCell className="text-right">
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Actions for ${agent.name}`}
              />
            }
          >
            <Ellipsis aria-hidden="true" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-36">
            <DropdownMenuItem onClick={() => onView(agent.id)}>
              <Eye aria-hidden="true" />
              View
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onEdit(agent.id)}>
              <Pencil aria-hidden="true" />
              Edit
            </DropdownMenuItem>
            <DropdownMenuItem
              className="text-destructive"
              disabled={agent.publishedRevision != null}
              title={
                agent.publishedRevision == null
                  ? "Delete draft Agent"
                  : "Published Agents are retained for audit and durable runs"
              }
              onClick={() => onDelete(agent)}
            >
              <Trash2 aria-hidden="true" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
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
  field: AgentSortField;
  label: string;
  onSort: (field: AgentSortField) => void;
  query: AgentCollectionQuery;
}) {
  const isActive = query.sortBy === field;
  const ariaSort = isActive
    ? query.direction === "asc"
      ? "ascending"
      : "descending"
    : "none";
  const Icon = !isActive
    ? ArrowUpDown
    : query.direction === "asc"
      ? ArrowUp
      : ArrowDown;

  return (
    <TableHead className={className} aria-sort={ariaSort}>
      <Button
        className="-ml-2"
        variant="ghost"
        size="sm"
        onClick={() => onSort(field)}
      >
        {label}
        <Icon className="text-muted-foreground" aria-hidden="true" />
      </Button>
    </TableHead>
  );
}

function AgentLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-36" />
        <Skeleton className="mt-2 h-3 w-24" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-full max-w-72" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-16" />
      </TableCell>
      <TableCell className="hidden sm:table-cell">
        <Skeleton className="h-4 w-32" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}

function getPaginationLabel(
  page: number,
  limit: number,
  itemCount: number,
  total: number,
): string {
  if (itemCount === 0) {
    return "No Agents";
  }

  const first = (page - 1) * limit + 1;
  const last = first + itemCount - 1;
  return `${first}–${last} of ${total} Agents`;
}

export { AgentsTable };
