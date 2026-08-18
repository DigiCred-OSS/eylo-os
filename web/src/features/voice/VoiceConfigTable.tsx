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
import { formatVoiceDate } from "@/features/voice/voice-formatters";
import {
  hasVoiceCollectionFilters,
  voiceRuntimeMode,
} from "@/features/voice/voice.query";
import type {
  VoiceCollectionQuery,
  VoiceConfigRecord,
  VoiceSortField,
} from "@/features/voice/voice.types";

interface VoiceConfigTableProps {
  items: readonly VoiceConfigRecord[];
  onClearFilters: () => void;
  onDelete: (voiceConfig: VoiceConfigRecord) => void;
  onEdit: (voiceConfigId: string) => void;
  onRetry: () => void;
  onSort: (field: VoiceSortField) => void;
  onView: (voiceConfigId: string) => void;
  query: VoiceCollectionQuery;
}

const VoiceConfigTable = observer(function VoiceConfigTable({
  items,
  onClearFilters,
  onDelete,
  onEdit,
  onRetry,
  onSort,
  onView,
  query,
}: VoiceConfigTableProps) {
  const { voice } = useRootStore();
  if (voice.collectionErrorMessage !== null && voice.items.length === 0) {
    return (
      <div className="border py-16 text-center" role="alert">
        <p className="text-sm font-medium">Voice Configs are unavailable</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {voice.collectionErrorMessage}
        </p>
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  const hasFilters = hasVoiceCollectionFilters(query);
  if (!voice.isCollectionLoading && items.length === 0) {
    return (
      <div className="border py-16 text-center">
        <p className="text-sm font-medium">
          {hasFilters
            ? "No Voice Configs match these filters"
            : "No Voice Configs yet"}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          {hasFilters
            ? "Change or clear the filters to see other configs."
            : "Create a reusable voice experience, then assign it to an Agent."}
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
        aria-label="Voice Configs"
      >
        {voice.isCollectionLoading && voice.items.length === 0
          ? Array.from({ length: 5 }, (_, index) => (
              <VoiceLoadingCard key={index} />
            ))
          : items.map((voiceConfig) => (
              <VoiceConfigCard
                key={voiceConfig.id}
                voiceConfig={voiceConfig}
                onDelete={onDelete}
                onEdit={onEdit}
                onView={onView}
              />
            ))}
      </div>

      <Table className="hidden sm:table" aria-label="Voice Configs">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <SortableHead
              field="name"
              label="Name"
              query={query}
              onSort={onSort}
            />
            <TableHead>Runtime</TableHead>
            <SortableHead
              className="hidden md:table-cell"
              field="revision"
              label="Revision"
              query={query}
              onSort={onSort}
            />
            <TableHead className="hidden lg:table-cell">Recording</TableHead>
            <SortableHead
              className="hidden md:table-cell"
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
          {voice.isCollectionLoading && voice.items.length === 0
            ? Array.from({ length: 6 }, (_, index) => (
                <VoiceLoadingRow key={index} />
              ))
            : items.map((voiceConfig) => (
                <VoiceConfigRow
                  key={voiceConfig.id}
                  voiceConfig={voiceConfig}
                  onDelete={onDelete}
                  onEdit={onEdit}
                  onView={onView}
                />
              ))}
        </TableBody>
      </Table>
      {!voice.isCollectionLoading ? (
        <p className="border-t px-3 py-3 text-xs text-muted-foreground">
          {items.length === 1
            ? "1 Voice Config"
            : `${items.length} Voice Configs`}
        </p>
      ) : null}
    </div>
  );
});

function VoiceConfigRow({
  onDelete,
  onEdit,
  onView,
  voiceConfig,
}: {
  onDelete: (voiceConfig: VoiceConfigRecord) => void;
  onEdit: (voiceConfigId: string) => void;
  onView: (voiceConfigId: string) => void;
  voiceConfig: VoiceConfigRecord;
}) {
  const updatedAt = formatVoiceDate(voiceConfig.updated_at);
  return (
    <TableRow>
      <TableCell className="max-w-80 whitespace-normal">
        <button
          className="break-words text-left font-medium underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-2"
          type="button"
          onClick={() => onView(voiceConfig.id)}
        >
          {voiceConfig.name}
        </button>
        {voiceConfig.description === null ? null : (
          <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
            {voiceConfig.description}
          </p>
        )}
      </TableCell>
      <TableCell>
        <Badge variant="outline">{runtimeLabel(voiceConfig)}</Badge>
      </TableCell>
      <TableCell className="hidden text-muted-foreground md:table-cell">
        {voiceConfig.revision}
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Badge variant="outline">
          {voiceConfig.config.artifacts?.audio_storage_enabled
            ? "Stored"
            : "Not stored"}
        </Badge>
      </TableCell>
      <TableCell className="hidden text-muted-foreground md:table-cell">
        <DateValue value={updatedAt} />
      </TableCell>
      <TableCell className="text-right">
        <VoiceActions
          voiceConfig={voiceConfig}
          onDelete={onDelete}
          onEdit={onEdit}
          onView={onView}
        />
      </TableCell>
    </TableRow>
  );
}

function VoiceConfigCard({
  onDelete,
  onEdit,
  onView,
  voiceConfig,
}: {
  onDelete: (voiceConfig: VoiceConfigRecord) => void;
  onEdit: (voiceConfigId: string) => void;
  onView: (voiceConfigId: string) => void;
  voiceConfig: VoiceConfigRecord;
}) {
  const updatedAt = formatVoiceDate(voiceConfig.updated_at);
  return (
    <div className="p-4" role="listitem">
      <div className="flex items-start justify-between gap-3">
        <button
          className="min-w-0 break-words text-left font-medium underline-offset-4 hover:underline"
          type="button"
          onClick={() => onView(voiceConfig.id)}
        >
          {voiceConfig.name}
        </button>
        <VoiceActions
          voiceConfig={voiceConfig}
          onDelete={onDelete}
          onEdit={onEdit}
          onView={onView}
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge variant="outline">{runtimeLabel(voiceConfig)}</Badge>
        <Badge variant="outline">Revision {voiceConfig.revision}</Badge>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Updated <DateValue value={updatedAt} />
      </p>
    </div>
  );
}

function VoiceActions({
  onDelete,
  onEdit,
  onView,
  voiceConfig,
}: {
  onDelete: (voiceConfig: VoiceConfigRecord) => void;
  onEdit: (voiceConfigId: string) => void;
  onView: (voiceConfigId: string) => void;
  voiceConfig: VoiceConfigRecord;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            aria-label={`Actions for ${voiceConfig.name}`}
          />
        }
      >
        <Ellipsis aria-hidden="true" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onView(voiceConfig.id)}>
          <Eye aria-hidden="true" />
          View
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onEdit(voiceConfig.id)}>
          <Pencil aria-hidden="true" />
          Edit
        </DropdownMenuItem>
        <DropdownMenuItem
          variant="destructive"
          onClick={() => onDelete(voiceConfig)}
        >
          <Trash2 aria-hidden="true" />
          Delete
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
  field: VoiceSortField;
  label: string;
  onSort: (field: VoiceSortField) => void;
  query: VoiceCollectionQuery;
}) {
  const active = query.sortBy === field;
  const Icon = active
    ? query.direction === "asc"
      ? ArrowUp
      : ArrowDown
    : ArrowUpDown;
  return (
    <TableHead className={className}>
      <Button
        className="h-auto px-0 font-medium"
        variant="ghost"
        onClick={() => onSort(field)}
      >
        {label}
        <Icon className="size-3.5" aria-hidden="true" />
      </Button>
    </TableHead>
  );
}

function runtimeLabel(voiceConfig: VoiceConfigRecord): string {
  return voiceRuntimeMode(voiceConfig) === "realtime"
    ? "Realtime"
    : "Decomposed";
}

function DateValue({
  value,
}: {
  value: { exact: string | null; label: string };
}) {
  return value.exact === null ? (
    value.label
  ) : (
    <time dateTime={value.exact} title={`${value.exact} (UTC)`}>
      {value.label}
    </time>
  );
}

function VoiceLoadingRow() {
  return (
    <TableRow>
      <TableCell>
        <Skeleton className="h-4 w-40" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-24" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-10" />
      </TableCell>
      <TableCell className="hidden lg:table-cell">
        <Skeleton className="h-5 w-20" />
      </TableCell>
      <TableCell className="hidden md:table-cell">
        <Skeleton className="h-4 w-20" />
      </TableCell>
      <TableCell>
        <Skeleton className="ml-auto size-8" />
      </TableCell>
    </TableRow>
  );
}

function VoiceLoadingCard() {
  return (
    <div className="space-y-3 p-4">
      <Skeleton className="h-4 w-44" />
      <Skeleton className="h-5 w-24" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

export { VoiceConfigTable };
