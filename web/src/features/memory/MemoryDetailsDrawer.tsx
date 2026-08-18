import { X } from "lucide-react";
import { observer } from "mobx-react-lite";
import type { ReactNode } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Skeleton } from "@/components/ui/skeleton";
import {
  formatMemoryDate,
  formatMemoryLevel,
  formatMemoryRelationship,
  formatMemoryStatus,
  formatReconciliationState,
} from "@/features/memory/memory-formatters";
import { MemoryIntegrityBadge } from "@/features/memory/MemoryIntegrityBadge";
import type { MemoryDetail } from "@/features/memory/memory.types";

interface MemoryDetailsDrawerProps {
  memoryId: string | undefined;
  onClose: () => void;
}

const MemoryDetailsDrawer = observer(function MemoryDetailsDrawer({
  memoryId,
  onClose,
}: MemoryDetailsDrawerProps) {
  const { memory } = useRootStore();
  const selected = memory.selectedMemory;

  return (
    <Drawer
      open={memoryId !== undefined}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
      swipeDirection="right"
    >
      <DrawerContent className="[--drawer-content-width:min(100%,46rem)]">
        <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
          <DrawerTitle>Memory details</DrawerTitle>
          <DrawerDescription>
            Integrity, related facts, lifecycle, provenance, and durable
            history.
          </DrawerDescription>
        </DrawerHeader>
        <Button
          className="absolute top-4 right-4 z-20"
          variant="ghost"
          size="icon"
          aria-label="Close memory details"
          title="Close"
          onClick={onClose}
        >
          <X aria-hidden="true" />
        </Button>

        <div className="min-h-0 min-w-0 flex-1 overflow-y-auto p-5">
          {memory.isSelectedLoading && selected === null ? (
            <MemoryDetailsSkeleton />
          ) : memory.selectedErrorMessage !== null ? (
            <div
              className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
              role="alert"
            >
              {memory.selectedErrorMessage}
            </div>
          ) : selected !== null ? (
            <MemoryDetails memory={selected} />
          ) : null}
        </div>
      </DrawerContent>
    </Drawer>
  );
});

function MemoryDetails({ memory }: { memory: MemoryDetail }) {
  const provenance = memory.provenance;
  return (
    <div className="min-w-0 space-y-8">
      <DetailsSection title="Remembered fact">
        <p className="break-words text-sm leading-6 whitespace-pre-wrap">
          {memory.content}
        </p>
      </DetailsSection>

      <DetailsSection title="Lifecycle">
        <dl>
          <DetailRow label="Integrity">
            <MemoryIntegrityBadge integrity={memory.integrity} />
          </DetailRow>
          <DetailRow label="Status">
            <Badge
              variant={memory.status === "expired" ? "secondary" : "outline"}
            >
              {formatMemoryStatus(memory.status)}
            </Badge>
          </DetailRow>
          <DetailRow label="Saved">
            <DateValue value={formatMemoryDate(memory.created_at)} />
          </DetailRow>
          <DetailRow label="Updated">
            <DateValue value={formatMemoryDate(memory.updated_at)} />
          </DetailRow>
          <DetailRow label="Recall count">{memory.recall_count}</DetailRow>
          <DetailRow label="Last recalled">
            <DateValue value={formatMemoryDate(memory.last_recalled_at)} />
          </DetailRow>
          <DetailRow label="Expired">
            <DateValue value={formatMemoryDate(memory.expires_at)} />
          </DetailRow>
        </dl>
      </DetailsSection>

      <DetailsSection title="Related facts">
        {memory.relationships.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No reconciliation relationships recorded.
          </p>
        ) : (
          <ol className="divide-y border-y">
            {memory.relationships.map((relationship) => (
              <li key={relationship.id} className="min-w-0 space-y-3 py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">
                    {formatMemoryRelationship(relationship)}
                  </Badge>
                  <Badge
                    variant={relationship.current ? "outline" : "secondary"}
                  >
                    {relationship.current ? "Current" : "Historical"}
                  </Badge>
                </div>
                <p className="break-words text-sm leading-6 whitespace-pre-wrap">
                  {relationship.related_memory.content}
                </p>
                <dl>
                  <DetailRow label="Related integrity">
                    <MemoryIntegrityBadge
                      integrity={relationship.related_memory.integrity}
                    />
                  </DetailRow>
                  <DetailRow label="Related level">
                    <Badge variant="outline">
                      {formatMemoryLevel(relationship.related_memory.level)}
                    </Badge>
                  </DetailRow>
                  <DetailRow label="Related memory ID">
                    <CodeValue>{relationship.related_memory.id}</CodeValue>
                  </DetailRow>
                  <DetailRow label="Detected">
                    <DateValue
                      value={formatMemoryDate(relationship.created_at)}
                    />
                  </DetailRow>
                  <DetailRow label="Reconciliation job">
                    <CodeValue>{relationship.reconciliation_job_id}</CodeValue>
                  </DetailRow>
                </dl>
              </li>
            ))}
          </ol>
        )}
      </DetailsSection>

      {memory.latest_reconciliation === null ? null : (
        <DetailsSection title="Latest reconciliation">
          <ReconciliationDetails job={memory.latest_reconciliation} />
        </DetailsSection>
      )}

      <DetailsSection title="Ownership">
        <dl>
          <DetailRow label="Level">
            <Badge variant="outline">{formatMemoryLevel(memory.level)}</Badge>
          </DetailRow>
          <DetailRow label="Subject">{memory.subject_label}</DetailRow>
          <DetailRow label="Subject ID">
            <CodeValue>{memory.subject_id}</CodeValue>
          </DetailRow>
          <DetailRow label="Memory ID">
            <CodeValue>{memory.id}</CodeValue>
          </DetailRow>
        </dl>
      </DetailsSection>

      <DetailsSection title="Provenance">
        <dl>
          <DetailRow label="Origin">
            <Badge variant="outline">
              {formatIdentifier(provenance.origin)}
            </Badge>
          </DetailRow>
          <DetailRow label="Source conversation">
            <CodeValue>{memory.source_conversation_id}</CodeValue>
          </DetailRow>
          <DetailRow label="Actor">
            {provenance.actor === null ? (
              "Automatic formation"
            ) : (
              <Badge variant="outline">
                {formatIdentifier(provenance.actor.kind)}
              </Badge>
            )}
          </DetailRow>
          {provenance.actor === null ? null : (
            <>
              <DetailRow label="Actor ID">
                <CodeValue>{provenance.actor.actor_id}</CodeValue>
              </DetailRow>
              <DetailRow label="Agent revision">
                {provenance.actor.agent_revision ?? "Not applicable"}
              </DetailRow>
            </>
          )}
          <DetailRow label="Extraction model">
            {provenance.extraction?.model ?? "Direct Agent action"}
          </DetailRow>
          <DetailRow label="Source messages">
            {provenance.source_messages.length === 0 ? (
              "Not recorded"
            ) : (
              <ul className="space-y-1">
                {provenance.source_messages.map((source) => (
                  <li key={source.message_id}>
                    <CodeValue>{source.message_id}</CodeValue>
                  </li>
                ))}
              </ul>
            )}
          </DetailRow>
        </dl>
      </DetailsSection>

      <DetailsSection title="History">
        {memory.history.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No lifecycle events recorded.
          </p>
        ) : (
          <ol className="divide-y border-y">
            {memory.history.map((change) => (
              <li key={change.id} className="space-y-2 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Badge variant="outline">
                    {formatIdentifier(change.event)}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {formatMemoryDate(change.created_at).label}
                  </span>
                </div>
                {change.before === null ? null : (
                  <HistoryValue label="Before" value={change.before} />
                )}
                {change.after === null ? null : (
                  <HistoryValue label="After" value={change.after} />
                )}
                <HistoryProvenance change={change} />
              </li>
            ))}
          </ol>
        )}
      </DetailsSection>

      {Object.keys(memory.metadata).length === 0 ? null : (
        <DetailsSection title="Metadata">
          <pre className="break-all border bg-muted/40 p-3 text-xs whitespace-pre-wrap">
            {JSON.stringify(memory.metadata, null, 2)}
          </pre>
        </DetailsSection>
      )}
    </div>
  );
}

function ReconciliationDetails({
  job,
}: {
  job: NonNullable<MemoryDetail["latest_reconciliation"]>;
}) {
  return (
    <dl>
      <DetailRow label="State">
        <Badge variant={job.state === "failed" ? "destructive" : "outline"}>
          {formatReconciliationState(job.state)}
        </Badge>
      </DetailRow>
      <DetailRow label="Job ID">
        <CodeValue>{job.id}</CodeValue>
      </DetailRow>
      <DetailRow label="Generation">{job.generation}</DetailRow>
      <DetailRow label="Changes considered">{job.change_count}</DetailRow>
      <DetailRow label="Outcomes">
        <span className="break-words">
          {job.duplicate_count} duplicate · {job.superseded_count} superseded ·{" "}
          {job.conflict_count} conflict · {job.unrelated_count} unrelated ·{" "}
          {job.failed_count} failed
        </span>
      </DetailRow>
      <DetailRow label="Attempts">{job.attempts}</DetailRow>
      <DetailRow label="Started">
        <DateValue value={formatMemoryDate(job.started_at)} />
      </DetailRow>
      <DetailRow label="Finished">
        <DateValue value={formatMemoryDate(job.finished_at)} />
      </DetailRow>
      {job.last_error === null ? null : (
        <DetailRow label="Failure">
          {formatIdentifier(job.last_error)}
        </DetailRow>
      )}
    </dl>
  );
}

function DetailsSection({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <section className="min-w-0 space-y-3">
      <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
      </h2>
      {children}
    </section>
  );
}

function DetailRow({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="grid min-w-0 gap-1 border-t py-3 first:border-t-0 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-sm leading-5">{children}</dd>
    </div>
  );
}

function CodeValue({ children }: { children: ReactNode }) {
  return (
    <code className="break-all rounded-sm bg-muted px-1 py-0.5 text-xs">
      {children}
    </code>
  );
}

function HistoryValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 text-xs sm:grid-cols-[4rem_minmax(0,1fr)]">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-words whitespace-pre-wrap">{value}</span>
    </div>
  );
}

function HistoryProvenance({
  change,
}: {
  change: MemoryDetail["history"][number];
}) {
  const actor = change.provenance.actor;
  return (
    <dl className="grid min-w-0 gap-x-3 gap-y-1 border-t pt-2 text-xs sm:grid-cols-[7rem_minmax(0,1fr)]">
      <dt className="text-muted-foreground">Origin</dt>
      <dd>{formatIdentifier(change.provenance.origin)}</dd>
      <dt className="text-muted-foreground">Source</dt>
      <dd className="min-w-0">
        {change.source_conversation_id === null ? (
          "Not recorded"
        ) : (
          <CodeValue>{change.source_conversation_id}</CodeValue>
        )}
      </dd>
      <dt className="text-muted-foreground">Actor</dt>
      <dd className="min-w-0">
        {actor === null ? (
          "Automatic formation"
        ) : (
          <span className="break-words">
            {formatIdentifier(actor.kind)} ·{" "}
            <CodeValue>{actor.actor_id}</CodeValue>
          </span>
        )}
      </dd>
      <dt className="text-muted-foreground">Source messages</dt>
      <dd className="min-w-0">
        {change.provenance.source_messages.length === 0 ? (
          "Not recorded"
        ) : (
          <ul className="space-y-1">
            {change.provenance.source_messages.map((source) => (
              <li key={source.message_id}>
                <CodeValue>{source.message_id}</CodeValue>
              </li>
            ))}
          </ul>
        )}
      </dd>
      <dt className="text-muted-foreground">Extraction</dt>
      <dd className="break-words">
        {change.provenance.extraction?.model ?? "Direct action"}
      </dd>
    </dl>
  );
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

function formatIdentifier(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/^./, (character) => character.toUpperCase());
}

function MemoryDetailsSkeleton() {
  return (
    <div className="space-y-8" aria-label="Loading memory details">
      {[0, 1, 2, 3].map((section) => (
        <div key={section} className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-16 w-full" />
        </div>
      ))}
    </div>
  );
}

export { MemoryDetailsDrawer };
