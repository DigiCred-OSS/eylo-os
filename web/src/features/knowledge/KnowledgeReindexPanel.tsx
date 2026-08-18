import { LoaderCircle, RefreshCw } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useState } from "react";

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
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  KnowledgeReindexStatus,
  Knowledgebase,
} from "@/features/knowledge/knowledge.types";

interface KnowledgeReindexPanelProps {
  knowledgebase: Knowledgebase;
  organizationId: string;
}

const KnowledgeReindexPanel = observer(function KnowledgeReindexPanel({
  knowledgebase,
  organizationId,
}: KnowledgeReindexPanelProps) {
  const { knowledge } = useRootStore();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedConfigId, setSelectedConfigId] = useState("");
  const status = knowledge.reindexStatus;
  const isRunning =
    status?.state === "reindexing" ||
    status?.latest_job?.state === "pending" ||
    status?.latest_job?.state === "running";

  function openDialog(): void {
    setSelectedConfigId(
      status?.target_space?.provider_config_id ??
        status?.available_space?.provider_config_id ??
        "",
    );
    setDialogOpen(true);
    void knowledge.loadReindexOptions();
  }

  async function confirmReindex(): Promise<void> {
    if (selectedConfigId === "") {
      return;
    }
    const succeeded = await knowledge.startKnowledgeReindex(
      organizationId,
      knowledgebase.id,
      selectedConfigId,
    );
    if (succeeded) {
      setDialogOpen(false);
    }
  }

  return (
    <section className="space-y-3" aria-labelledby="knowledge-index-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2
          id="knowledge-index-title"
          className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
        >
          Vector index
        </h2>
        {status === null ? null : <IndexStateBadge status={status} />}
      </div>

      {knowledge.isReindexStatusLoading && status === null ? (
        <div
          className="space-y-2 border-y py-3"
          aria-label="Loading vector index"
        >
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-full" />
        </div>
      ) : knowledge.reindexErrorMessage !== null && status === null ? (
        <div
          className="min-w-0 break-words border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
          role="alert"
        >
          {knowledge.reindexErrorMessage}
        </div>
      ) : status !== null ? (
        <div className="space-y-4 border-y py-4">
          <p className="text-sm leading-6 text-muted-foreground">
            {indexSummary(status)} Existing vectors remain active until every
            chunk is embedded and the new index is cut over atomically.
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

          {(knowledge.reindexErrorMessage ?? status.last_error) ? (
            <div
              className="min-w-0 break-words border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
              role="alert"
            >
              {knowledge.reindexErrorMessage ?? status.last_error}
            </div>
          ) : null}

          <Button
            size="sm"
            variant="outline"
            disabled={isRunning}
            onClick={openDialog}
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
                : "Reindex knowledgebase"}
          </Button>
        </div>
      ) : null}

      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          if (!knowledge.isReindexing) {
            setDialogOpen(open);
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Reindex knowledgebase</DialogTitle>
            <DialogDescription>
              Choose a ready embedding configuration. Queries continue using the
              active index until the durable job completes.
            </DialogDescription>
          </DialogHeader>

          <div className="min-w-0 space-y-2">
            <Label htmlFor="knowledge-reindex-embedding">
              Embedding configuration
            </Label>
            <Select
              value={selectedConfigId}
              disabled={
                knowledge.isReindexOptionsLoading || knowledge.isReindexing
              }
              onValueChange={(value) => setSelectedConfigId(value ?? "")}
            >
              <SelectTrigger
                id="knowledge-reindex-embedding"
                className="w-full min-w-0"
              >
                <SelectValue>
                  {selectedConfigId === ""
                    ? knowledge.isReindexOptionsLoading
                      ? "Loading configurations…"
                      : "Choose a ready configuration"
                    : configLabel(
                        knowledge.reindexEmbeddingConfigs.find(
                          (config) => config.id === selectedConfigId,
                        ),
                      )}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {knowledge.reindexEmbeddingConfigs.map((config) => (
                  <SelectItem key={config.id} value={config.id}>
                    {configLabel(config)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {knowledge.reindexOptionsErrorMessage !== null ? (
              <p className="text-sm text-destructive" role="alert">
                {knowledge.reindexOptionsErrorMessage}
              </p>
            ) : !knowledge.isReindexOptionsLoading &&
              knowledge.reindexEmbeddingConfigs.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No ready embedding configuration is available. Verify one in
                Providers first.
              </p>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              disabled={knowledge.isReindexing}
              onClick={() => setDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              disabled={selectedConfigId === "" || knowledge.isReindexing}
              onClick={() => void confirmReindex()}
            >
              {knowledge.isReindexing ? (
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

function IndexStateBadge({ status }: { status: KnowledgeReindexStatus }) {
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
  space: KnowledgeReindexStatus["active_space"];
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

function ProgressDetails({ status }: { status: KnowledgeReindexStatus }) {
  const job = status.latest_job;
  if (job === null) {
    return null;
  }
  const total = job.source_chunk_count;
  const completed = Math.min(job.indexed_chunk_count, total);
  const percent = total === 0 ? 0 : Math.round((completed / total) * 100);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
        <span className="capitalize">Job {job.state}</span>
        <span>
          {completed} of {total} chunks
        </span>
      </div>
      {total === 0 ? null : (
        <div
          className="h-1.5 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-label="Knowledgebase reindex progress"
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

function indexSummary(status: KnowledgeReindexStatus): string {
  if (status.state === "failed") {
    return "The latest reindex failed; the previous index is still serving queries.";
  }
  if (
    status.state === "reindexing" ||
    status.latest_job?.state === "pending" ||
    status.latest_job?.state === "running"
  ) {
    return "A durable reindex is queued or running.";
  }
  if (status.state === "reindex_required") {
    return "A different embedding space is staged and requires reindexing.";
  }
  if (status.update_available) {
    return "The bound embedding configuration now resolves to a different vector space.";
  }
  return "The active index matches its current embedding space.";
}

function configLabel(
  config:
    | {
        name: string;
        provider: string;
        revision: number;
      }
    | undefined,
): string {
  return config === undefined
    ? "Choose a ready configuration"
    : `${config.name} · ${config.provider} · revision ${config.revision}`;
}

export { KnowledgeReindexPanel };
