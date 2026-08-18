import { Ellipsis, Eye, Pencil } from "lucide-react";

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
  formatAutomationDate,
  formatAutomationEnum,
  formatRecurrence,
} from "@/features/automations/automation-formatters";
import { hasAutomationFilters } from "@/features/automations/automations.query";
import type {
  ScheduleCollectionQuery,
  ScheduleRecord,
} from "@/features/automations/automations.types";

interface AutomationsTableProps {
  errorMessage: string | null;
  isLoading: boolean;
  items: readonly ScheduleRecord[];
  onClearFilters: () => void;
  onEdit: (scheduleId: string) => void;
  onRetry: () => void;
  onView: (scheduleId: string) => void;
  query: ScheduleCollectionQuery;
}

function AutomationsTable({
  errorMessage,
  isLoading,
  items,
  onClearFilters,
  onEdit,
  onRetry,
  onView,
  query,
}: AutomationsTableProps) {
  if (errorMessage !== null) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Automations are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">{errorMessage}</p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }
  const hasFilters = hasAutomationFilters(query);
  if (!isLoading && items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters
            ? "No automations match these filters"
            : "No automations yet"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to inspect other schedules."
            : "Create an automation to trigger a published Agent at an explicit time."}
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
      <div className="divide-y sm:hidden" role="list" aria-label="Automations">
        {isLoading
          ? Array.from({ length: 5 }, (_, index) => <LoadingCard key={index} />)
          : items.map((item) => (
              <AutomationCard
                key={item.id}
                schedule={item}
                onEdit={onEdit}
                onView={onView}
              />
            ))}
      </div>
      <Table className="hidden table-fixed sm:table" aria-label="Automations">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[28%]">Automation</TableHead>
            <TableHead className="w-32">State</TableHead>
            <TableHead className="hidden md:table-cell">Action</TableHead>
            <TableHead className="hidden w-40 lg:table-cell">
              Recurrence
            </TableHead>
            <TableHead className="w-44">Next run</TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading
            ? Array.from({ length: 6 }, (_, index) => (
                <LoadingRow key={index} />
              ))
            : items.map((item) => (
                <AutomationRow
                  key={item.id}
                  schedule={item}
                  onEdit={onEdit}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>
      <div className="border-t px-3 py-3 text-xs text-muted-foreground">
        {isLoading
          ? "Loading automations…"
          : `${items.length} automation${items.length === 1 ? "" : "s"}`}
      </div>
    </div>
  );
}

function AutomationRow({
  schedule,
  onEdit,
  onView,
}: {
  schedule: ScheduleRecord;
  onEdit: (id: string) => void;
  onView: (id: string) => void;
}) {
  const next = formatAutomationDate(schedule.next_at);
  return (
    <TableRow>
      <TableCell className="min-w-0 whitespace-normal">
        <button
          className="max-w-full break-words text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(schedule.id)}
        >
          {schedule.name}
        </button>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {schedule.key}
        </p>
      </TableCell>
      <TableCell>
        <Badge variant="outline">
          {formatAutomationEnum(schedule.lifecycle)}
        </Badge>
      </TableCell>
      <TableCell className="hidden whitespace-normal md:table-cell">
        <code className="break-all text-xs">{schedule.action}</code>
      </TableCell>
      <TableCell className="hidden whitespace-normal lg:table-cell">
        {formatRecurrence(schedule.rule)}
      </TableCell>
      <TableCell className="whitespace-normal">
        {schedule.next_at === null ? (
          next.label
        ) : (
          <time dateTime={schedule.next_at} title={next.title}>
            {next.label}
          </time>
        )}
      </TableCell>
      <TableCell className="text-right">
        <AutomationActions
          schedule={schedule}
          onEdit={onEdit}
          onView={onView}
        />
      </TableCell>
    </TableRow>
  );
}

function AutomationCard({
  schedule,
  onEdit,
  onView,
}: {
  schedule: ScheduleRecord;
  onEdit: (id: string) => void;
  onView: (id: string) => void;
}) {
  const next = formatAutomationDate(schedule.next_at);
  return (
    <article className="space-y-3 p-4" role="listitem">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <button
            className="break-words text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
            type="button"
            onClick={() => onView(schedule.id)}
          >
            {schedule.name}
          </button>
          <p className="mt-0.5 break-all text-xs text-muted-foreground">
            {schedule.key}
          </p>
        </div>
        <AutomationActions
          schedule={schedule}
          onEdit={onEdit}
          onView={onView}
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge variant="outline">
          {formatAutomationEnum(schedule.lifecycle)}
        </Badge>
        <Badge variant="outline">{formatRecurrence(schedule.rule)}</Badge>
      </div>
      <p className="text-sm text-muted-foreground">Next: {next.label}</p>
    </article>
  );
}

function AutomationActions({
  schedule,
  onEdit,
  onView,
}: {
  schedule: ScheduleRecord;
  onEdit: (id: string) => void;
  onView: (id: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Actions for ${schedule.name}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onView(schedule.id)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
        <DropdownMenuItem
          disabled={!schedule.enabled}
          onClick={() => onEdit(schedule.id)}
        >
          <Pencil aria-hidden="true" />
          Edit
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function LoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-36" />
        <Skeleton className="mt-2 h-3 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-32" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-4 w-24" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-28" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}
function LoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-3 w-28" />
      <Skeleton className="h-5 w-36" />
    </div>
  );
}

export { AutomationsTable };
