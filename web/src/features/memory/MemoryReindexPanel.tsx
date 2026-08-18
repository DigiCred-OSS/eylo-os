import { LoaderCircle, RefreshCw } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useState } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import type { MemoryReindexStatus } from "@/features/memory/memory.types";
import type { ProviderConfigRecord } from "@/features/providers/providers.types";

const MemoryReindexPanel = observer(function MemoryReindexPanel({
  config,
}: {
  config: ProviderConfigRecord;
}) {
  const { memory } = useRootStore();
  const [dialogOpen, setDialogOpen] = useState(false);
  const isCurrentConfig = memory.reindexConfigId === config.id;
  const status = isCurrentConfig ? memory.reindexStatus : null;
  const errorMessage = isCurrentConfig ? memory.reindexErrorMessage : null;
  const plannedTarget = status?.target_space ?? status?.available_space ?? null;
  const isRunning =
    status?.state === "reindexing" ||
    status?.latest_job?.state === "pending" ||
    status?.latest_job?.state === "running";

  useEffect(() => {
    void memory.loadReindexStatus(config.id);
    return memory.clearReindexStatus;
  }, [config.id, config.revision, config.verifiedAt, memory]);

  async function confirmReindex(): Promise<void> {
    const succeeded = await memory.startReindex(config.id);
    if (succeeded) {
      setDialogOpen(false);
    }
  }

  return (
    <section className="space-y-3" aria-labelledby="memory-index-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2
          id="memory-index-title"
          className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
        >
          Memory vector index
        </h2>
        {status === null ? null : <IndexStateBadge status={status} />}
      </div>

      {isCurrentConfig && memory.isReindexStatusLoading && status === null ? (
        <div
          className="space-y-2 border-y py-3"
          aria-label="Loading Memory index"
        >
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-full" />
        </div>
      ) : errorMessage !== null && status === null ? (
        <div
          className="min-w-0 break-words border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
          role="alert"
        >
          {errorMessage}
        </div>
      ) : status !== null && !status.initialized ? (
        <div className="border-y py-4 text-sm leading-6 text-muted-foreground">
          Verify this Memory configuration to initialize its embedding index.
        </div>
      ) : status !== null && status.active_space !== null ? (
        <div className="space-y-4 border-y py-4">
          <p className="text-sm leading-6 text-muted-foreground">
            {indexSummary(status)} Existing facts remain searchable until every
            active fact is embedded and the new index is cut over atomically.
          </p>

          <dl className="grid gap-3 sm:grid-cols-2">
            <SpaceDetails label="Active space" space={status.active_space} />
            {status.target_space === null ? null : (
              <SpaceDetails label="Target space" space={status.target_space} />
            )}
            {status.update_available && status.available_space !== null ? (
              <SpaceDetails
                label="Available space"
                space={status.available_space}
              />
            ) : null}
          </dl>

          {status.latest_job === null ? null : (
            <ProgressDetails status={status} />
          )}

          {(errorMessage ?? status.last_error) ? (
            <div
              className="min-w-0 break-words border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
              role="alert"
            >
              {errorMessage ?? status.last_error}
            </div>
          ) : null}

          {status.update_available ||
          status.state === "reindex_required" ||
          status.state === "failed" ||
          isRunning ? (
            <Button
              size="sm"
              variant="outline"
              disabled={isRunning}
              onClick={() => setDialogOpen(true)}
            >
              {isRunning ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw aria-hidden="true" />
              )}
              {isRunning
                ? "Reindex in progress"
                : status.state === "failed"
                  ? "Retry reindex"
                  : "Reindex memories"}
            </Button>
          ) : null}
        </div>
      ) : null}

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          if (!memory.isReindexing) {
            setDialogOpen(open);
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Reindex memories</DialogTitle>
            <DialogDescription>
              Start a durable reindex using this Memory configuration&apos;s
              verified embedding mapping. Recall continues against the active
              space until atomic cutover.
            </DialogDescription>
          </DialogHeader>
          {plannedTarget === null ? null : (
            <div className="min-w-0 break-words border bg-muted/40 p-3 text-sm leading-6">
              Target: <strong>{plannedTarget.model}</strong> ·{" "}
              {plannedTarget.dimensions} dimensions · revision{" "}
              {plannedTarget.provider_config_revision}
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              disabled={plannedTarget === null || memory.isReindexing}
              onClick={() => setDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              disabled={memory.isReindexing}
              onClick={() => void confirmReindex()}
            >
              {memory.isReindexing ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw aria-hidden="true" />
              )}
              Start durable reindex
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
});

function IndexStateBadge({ status }: { status: MemoryReindexStatus }) {
  if (!status.initialized) {
    return <Badge variant="secondary">Not initialized</Badge>;
  }
  const jobState = status.latest_job?.state;
  if (jobState === "pending") {
    return <Badge variant="secondary">Queued</Badge>;
  }
  if (status.state === "reindexing" || jobState === "running") {
    return <Badge variant="outline">Reindexing</Badge>;
  }
  if (status.state === "failed" || jobState === "failed") {
    return <Badge variant="destructive">Failed</Badge>;
  }
  if (status.state === "reindex_required" || status.update_available) {
    return <Badge variant="outline">Reindex required</Badge>;
  }
  return <Badge variant="outline">Current</Badge>;
}

function SpaceDetails({
  label,
  space,
}: {
  label: string;
  space: NonNullable<MemoryReindexStatus["active_space"]>;
}) {
  return (
    <div className="min-w-0 border p-3">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="mt-1 min-w-0 text-sm">
        <span className="block break-words font-medium">{space.model}</span>
        <span className="block break-words text-muted-foreground">
          {space.provider} · {space.dimensions} dimensions · revision{" "}
          {space.provider_config_revision}
        </span>
      </dd>
    </div>
  );
}

function ProgressDetails({ status }: { status: MemoryReindexStatus }) {
  const job = status.latest_job;
  if (job === null) {
    return null;
  }
  const total = job.source_fact_count;
  const completed = Math.min(job.indexed_fact_count, total);
  const percent = total === 0 ? 0 : Math.round((completed / total) * 100);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
        <span className="capitalize">Job {job.state}</span>
        <span>
          {completed} of {total} facts
        </span>
      </div>
      {total === 0 ? null : (
        <div
          className="h-1.5 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-label="Memory reindex progress"
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={completed}
        >
          <div
            className="h-full bg-foreground transition-[width]"
            style={{ width: `${percent}%` }}
          />
        </div>
      )}
    </div>
  );
}

function indexSummary(status: MemoryReindexStatus): string {
  if (status.state === "failed") {
    return "The latest reindex failed; the previous vectors still serve recall.";
  }
  if (
    status.state === "reindexing" ||
    status.latest_job?.state === "pending" ||
    status.latest_job?.state === "running"
  ) {
    return "A durable Memory reindex is queued or running.";
  }
  if (status.state === "reindex_required") {
    return "A different embedding space is staged and requires reindexing.";
  }
  if (status.update_available) {
    return "The verified Memory configuration now resolves to a different vector space.";
  }
  return "The active Memory index matches its verified embedding space.";
}

export { MemoryReindexPanel };
