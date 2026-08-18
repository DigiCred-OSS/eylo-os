import { Ellipsis, Eye } from "lucide-react";

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
  formatToolDate,
  formatToolEnum,
} from "@/features/tools/tool-formatters";
import { hasToolsFilters } from "@/features/tools/tools.query";
import type {
  ToolCollectionQuery,
  ToolRecord,
  ToolSource,
} from "@/features/tools/tools.types";

interface ToolsTableProps {
  errorMessage: string | null;
  isLoading: boolean;
  items: readonly ToolRecord[];
  onClearFilters: () => void;
  onRetry: () => void;
  onView: (toolId: string) => void;
  query: ToolCollectionQuery;
  source: ToolSource;
}

function ToolsTable({
  errorMessage,
  isLoading,
  items,
  onClearFilters,
  onRetry,
  onView,
  query,
  source,
}: ToolsTableProps) {
  if (errorMessage !== null) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Tools are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">{errorMessage}</p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }
  const hasFilters = hasToolsFilters(query);
  if (!isLoading && items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters ? "No tools match these filters" : emptyTitle(source)}
        </p>
        <p className="mx-auto mt-1 max-w-lg text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to inspect other tools."
            : emptyDescription(source)}
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
      <div className="divide-y sm:hidden" role="list" aria-label="Tools">
        {isLoading
          ? Array.from({ length: 5 }, (_, index) => (
              <ToolLoadingCard key={index} />
            ))
          : items.map((tool) => (
              <ToolCard
                key={tool.id}
                source={source}
                tool={tool}
                onView={onView}
              />
            ))}
      </div>
      <Table className="hidden table-fixed sm:table" aria-label="Tools">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[30%]">Tool</TableHead>
            <TableHead className="w-28">Kind</TableHead>
            <TableHead className="w-32">
              {source === "managed" ? "Lifecycle" : "Availability"}
            </TableHead>
            <TableHead className="hidden md:table-cell">Description</TableHead>
            <TableHead className="hidden w-36 lg:table-cell">
              Execution
            </TableHead>
            <TableHead className="hidden w-36 xl:table-cell">Updated</TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <ToolLoadingRow key={index} />
              ))
            : items.map((tool) => (
                <ToolRow
                  key={tool.id}
                  source={source}
                  tool={tool}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>
      <div className="border-t px-3 py-3 text-xs text-muted-foreground">
        {isLoading
          ? "Loading tools…"
          : `${items.length} tool${items.length === 1 ? "" : "s"}`}
      </div>
    </div>
  );
}

function ToolRow({
  onView,
  source,
  tool,
}: {
  onView: (toolId: string) => void;
  source: ToolSource;
  tool: ToolRecord;
}) {
  const updated = formatToolDate(tool.updatedAt);
  return (
    <TableRow>
      <TableCell className="min-w-0 whitespace-normal">
        <button
          className="max-w-full break-words text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(tool.id)}
        >
          {tool.displayName}
        </button>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {tool.name}
        </p>
      </TableCell>
      <TableCell>
        <Badge variant="outline">{formatToolEnum(tool.kind)}</Badge>
      </TableCell>
      <TableCell>
        <Badge variant="outline">{availabilityLabel(tool, source)}</Badge>
      </TableCell>
      <TableCell className="hidden whitespace-normal text-muted-foreground md:table-cell">
        <p className="line-clamp-2 leading-5">
          {tool.description || "No description"}
        </p>
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Badge variant="outline">{formatToolEnum(tool.executionMode)}</Badge>
      </TableCell>
      <TableCell className="hidden whitespace-normal text-muted-foreground xl:table-cell">
        {source !== "managed" ? (
          "Code-owned"
        ) : tool.updatedAt === undefined ? (
          updated.label
        ) : (
          <time dateTime={tool.updatedAt} title={updated.title}>
            {updated.label}
          </time>
        )}
      </TableCell>
      <TableCell className="text-right">
        <ToolActions
          label={tool.displayName}
          toolId={tool.id}
          onView={onView}
        />
      </TableCell>
    </TableRow>
  );
}

function ToolCard({
  onView,
  source,
  tool,
}: {
  onView: (toolId: string) => void;
  source: ToolSource;
  tool: ToolRecord;
}) {
  return (
    <article className="space-y-3 p-4" role="listitem">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            className="break-words text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
            type="button"
            onClick={() => onView(tool.id)}
          >
            {tool.displayName}
          </button>
          <p className="mt-0.5 break-all text-xs text-muted-foreground">
            {tool.name}
          </p>
        </div>
        <ToolActions
          label={tool.displayName}
          toolId={tool.id}
          onView={onView}
        />
      </div>
      <p className="line-clamp-3 text-sm leading-5 text-muted-foreground">
        {tool.description || "No description"}
      </p>
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">{formatToolEnum(tool.kind)}</Badge>
        <Badge variant="outline">{availabilityLabel(tool, source)}</Badge>
        <Badge variant="outline">{formatToolEnum(tool.executionMode)}</Badge>
      </div>
    </article>
  );
}

function ToolActions({
  label,
  onView,
  toolId,
}: {
  label: string;
  onView: (toolId: string) => void;
  toolId: string;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for ${label}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onView(toolId)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ToolLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-36" />
        <Skeleton className="mt-2 h-3 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-16" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-full" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-5 w-24" />
      </TableCell>
      <TableCell className="hidden xl:table-cell">
        <Skeleton className="h-4 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}

function ToolLoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-3 w-28" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-5 w-36" />
    </div>
  );
}

function emptyTitle(source: ToolSource): string {
  if (source === "provider") return "No tools for this provider capability";
  if (source === "managed") return "No managed tool definitions";
  return "No system tools are available";
}

function emptyDescription(source: ToolSource): string {
  if (source === "provider") {
    return "This capability does not expose any Agent-callable tools.";
  }
  if (source === "managed") {
    return "Managed definitions appear here when MCP or registered local tools are installed.";
  }
  return "System tools appear when their platform requirements are available.";
}

function availabilityLabel(tool: ToolRecord, source: ToolSource): string {
  return source === "managed" ? formatToolEnum(tool.lifecycle) : "Available";
}

export { ToolsTable };
