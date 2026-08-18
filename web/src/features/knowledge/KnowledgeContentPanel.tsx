import { FilePlus2, FolderInput, RefreshCw, X } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useState, type ReactNode } from "react";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { TERMINAL_STATES } from "@/features/knowledge/knowledge-content.store";
import { formatKnowledgeDate } from "@/features/knowledge/knowledge-formatters";
import type {
  CorpusImport,
  IngestionJob,
  KnowledgeDurableState,
} from "@/features/knowledge/knowledge.types";
import {
  providerCollectionPath,
  withReturnContext,
} from "@/features/providers/provider-navigation";
import { cn } from "@/lib/utils";

interface KnowledgeContentPanelProps {
  knowledgebaseId: string;
  memberKey: string;
  organizationId: string;
  returnTo: string;
}

const KnowledgeContentPanel = observer(function KnowledgeContentPanel({
  knowledgebaseId,
  memberKey,
  organizationId,
  returnTo,
}: KnowledgeContentPanelProps) {
  const { knowledge } = useRootStore();
  const content = knowledge.content;
  const [inlineOpen, setInlineOpen] = useState(false);
  const [corpusOpen, setCorpusOpen] = useState(false);

  useEffect(() => {
    void content.activate({ knowledgebaseId, memberKey, organizationId });
    return content.stop;
  }, [content, knowledgebaseId, memberKey, organizationId]);

  async function submitInline(): Promise<void> {
    if ((await content.submitInline()) !== null) {
      setInlineOpen(false);
    }
  }

  async function submitCorpus(): Promise<void> {
    if ((await content.submitCorpus()) !== null) {
      setCorpusOpen(false);
    }
  }

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">Content and ingestion</h2>
          <p className="mt-1 text-sm leading-5 text-muted-foreground">
            File work durably, then wait for a terminal state before relying on
            the document in Agent retrieval.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setCorpusOpen(true)}>
            <FolderInput aria-hidden="true" />
            Import storage
            {content.hasCorpusDraft ? <DraftMarker /> : null}
          </Button>
          <Button onClick={() => setInlineOpen(true)}>
            <FilePlus2 aria-hidden="true" />
            Add text
            {content.hasInlineDraft ? <DraftMarker /> : null}
          </Button>
        </div>
      </div>

      {content.workErrorMessage !== null ? (
        <div
          className="flex flex-wrap items-center justify-between gap-3 border border-warning/40 bg-warning/5 p-3"
          role="alert"
        >
          <p className="text-sm">{content.workErrorMessage}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void content.refresh()}
          >
            <RefreshCw aria-hidden="true" />
            Refresh
          </Button>
        </div>
      ) : null}

      {content.isMonitoring ? (
        <p
          className="flex items-center gap-2 text-xs text-muted-foreground"
          role="status"
        >
          <RefreshCw className="size-3 animate-spin" aria-hidden="true" />
          Watching active work
        </p>
      ) : null}

      {content.isLoading && !content.hasLoaded ? (
        <ContentSkeleton />
      ) : (
        <>
          <WorkSection
            empty="No documents have been filed yet."
            title="Document jobs"
          >
            {content.jobs.map((job) => (
              <IngestionJobCard
                key={job.id}
                isActing={content.actingIds.has(job.id)}
                job={job}
                onCancel={() => void content.cancelJob(job.id)}
              />
            ))}
          </WorkSection>

          <WorkSection
            empty="No storage corpus imports have been started."
            title="Corpus imports"
          >
            {content.corpusImports.map((corpusImport) => (
              <CorpusImportCard
                key={corpusImport.id}
                corpusImport={corpusImport}
                isActing={content.actingIds.has(corpusImport.id)}
                onCancel={() => void content.cancelCorpus(corpusImport.id)}
              />
            ))}
          </WorkSection>
        </>
      )}

      <InlineContentDialog
        open={inlineOpen}
        onOpenChange={setInlineOpen}
        onSubmit={submitInline}
      />
      <CorpusImportDialog
        open={corpusOpen}
        organizationId={organizationId}
        returnTo={returnTo}
        onOpenChange={setCorpusOpen}
        onSubmit={submitCorpus}
      />
    </div>
  );
});

const InlineContentDialog = observer(function InlineContentDialog({
  onOpenChange,
  onSubmit,
  open,
}: {
  onOpenChange: (open: boolean) => void;
  onSubmit: () => Promise<void>;
  open: boolean;
}) {
  const { knowledge } = useRootStore();
  const content = knowledge.content;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-2xl">
        <DialogHeader className="pr-8">
          <DialogTitle>Add text document</DialogTitle>
          <DialogDescription>
            Filing returns immediately. The worker chunks and indexes this text
            asynchronously.
          </DialogDescription>
        </DialogHeader>
        <form
          id="inline-content-form"
          className="min-h-0 space-y-5 overflow-y-auto pr-1"
          onSubmit={(event) => {
            event.preventDefault();
            void onSubmit();
          }}
        >
          <DialogMessage
            draftError={content.inlineDraftStorageErrorMessage}
            error={content.inlineErrorMessage}
            hasDraft={content.hasInlineDraft}
            savedAt={content.inlineSavedAt}
            onDiscard={content.discardInlineDraft}
          />
          <Field htmlFor="inline-content-title" label="Title" optional>
            <Input
              id="inline-content-title"
              maxLength={512}
              value={content.inlineValues.title}
              onChange={(event) =>
                content.setInlineField("title", event.target.value)
              }
            />
          </Field>
          <Field
            htmlFor="inline-content-source"
            label="Source URI"
            optional
            hint="A stable source address becomes document identity. Filing the same URI again replaces that document."
          >
            <Input
              id="inline-content-source"
              maxLength={4_096}
              autoComplete="off"
              spellCheck={false}
              placeholder="https://docs.example.com/refund-policy"
              value={content.inlineValues.sourceUri}
              onChange={(event) =>
                content.setInlineField("sourceUri", event.target.value)
              }
            />
          </Field>
          <Field
            htmlFor="inline-content-body"
            label="Content"
            hint={`${content.inlineValues.content.length.toLocaleString()} / 1,000,000 characters`}
          >
            <Textarea
              id="inline-content-body"
              required
              maxLength={1_000_000}
              rows={14}
              value={content.inlineValues.content}
              onChange={(event) =>
                content.setInlineField("content", event.target.value)
              }
            />
          </Field>
        </form>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={content.isSubmittingInline}
            onClick={() => onOpenChange(false)}
          >
            Close
          </Button>
          <Button
            type="submit"
            form="inline-content-form"
            disabled={content.isSubmittingInline}
          >
            {content.isSubmittingInline ? "Filing…" : "File ingestion"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
});

const CorpusImportDialog = observer(function CorpusImportDialog({
  onOpenChange,
  onSubmit,
  open,
  organizationId,
  returnTo,
}: {
  onOpenChange: (open: boolean) => void;
  onSubmit: () => Promise<void>;
  open: boolean;
  organizationId: string;
  returnTo: string;
}) {
  const { knowledge } = useRootStore();
  const content = knowledge.content;
  const selectedConfig = content.storageConfigs.find(
    (config) => config.id === content.corpusValues.storageProviderConfigId,
  );
  const storagePath = withReturnContext(
    providerCollectionPath(organizationId, "storage"),
    returnTo,
  );
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-xl">
        <DialogHeader className="pr-8">
          <DialogTitle>Import storage corpus</DialogTitle>
          <DialogDescription>
            Eylo sweeps one prefix, reports skipped objects, and files one
            durable document job per readable object.
          </DialogDescription>
        </DialogHeader>
        <form
          id="corpus-import-form"
          className="min-h-0 space-y-5 overflow-y-auto pr-1"
          onSubmit={(event) => {
            event.preventDefault();
            void onSubmit();
          }}
        >
          <DialogMessage
            draftError={content.corpusDraftStorageErrorMessage}
            error={content.corpusErrorMessage ?? content.storageErrorMessage}
            hasDraft={content.hasCorpusDraft}
            savedAt={content.corpusSavedAt}
            onDiscard={content.discardCorpusDraft}
          />
          <Field
            htmlFor="corpus-storage-config"
            label="Storage provider configuration"
            hint="Only ready configurations that can list and download objects are available. The current revision is pinned."
          >
            <Select
              value={content.corpusValues.storageProviderConfigId}
              onValueChange={(value) =>
                content.setCorpusField("storageProviderConfigId", value)
              }
            >
              <SelectTrigger id="corpus-storage-config" className="w-full">
                <SelectValue>
                  {selectedConfig === undefined
                    ? "Choose a ready configuration"
                    : `${selectedConfig.name} · ${selectedConfig.provider} · revision ${selectedConfig.revision}`}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {content.readyStorageConfigs.map((config) => (
                  <SelectItem key={config.id} value={config.id}>
                    {config.name} · {config.provider} · revision{" "}
                    {config.revision}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {content.readyStorageConfigs.length === 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">
                No applicable storage configuration. Configure and verify one in{" "}
                <a className="underline underline-offset-4" href={storagePath}>
                  Providers
                </a>
                .
              </p>
            ) : null}
          </Field>
          <Field
            htmlFor="corpus-prefix"
            label="Object prefix"
            optional
            hint="Prefix match, not a glob. Empty sweeps the configured storage root."
          >
            <Input
              id="corpus-prefix"
              maxLength={1_024}
              autoComplete="off"
              spellCheck={false}
              placeholder="policies/"
              value={content.corpusValues.prefix}
              onChange={(event) =>
                content.setCorpusField("prefix", event.target.value)
              }
            />
          </Field>
        </form>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={content.isSubmittingCorpus}
            onClick={() => onOpenChange(false)}
          >
            Close
          </Button>
          <Button
            type="submit"
            form="corpus-import-form"
            disabled={content.isSubmittingCorpus}
          >
            {content.isSubmittingCorpus ? "Starting…" : "Start import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
});

function IngestionJobCard({
  isActing,
  job,
  onCancel,
}: {
  isActing: boolean;
  job: IngestionJob;
  onCancel: () => void;
}) {
  const createdAt = formatKnowledgeDate(job.created_at);
  const startedAt = formatKnowledgeDate(job.started_at);
  const finishedAt = formatKnowledgeDate(job.finished_at);
  const source = job.source_uri ?? job.storage_key ?? "Inline content";
  return (
    <article className="space-y-3 border p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-medium">
            {job.title?.trim() || source}
          </h4>
          <p
            className="mt-1 truncate text-xs text-muted-foreground"
            title={source}
          >
            {source}
          </p>
        </div>
        <StateBadge state={job.state} />
      </div>
      <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
        <CompactValue
          label="Attempts"
          value={`${job.attempts} / ${job.max_attempts}`}
        />
        <CompactValue label="Filed" value={createdAt.label} />
        <CompactValue label="Started" value={startedAt.label} />
        <CompactValue label="Finished" value={finishedAt.label} />
        <CompactValue label="Document ID" value={job.document_id} code />
        <CompactValue label="Job ID" value={job.id} code />
      </dl>
      {job.last_error !== null ? (
        <p className="border border-destructive/30 bg-destructive/5 p-3 text-xs leading-5 text-destructive">
          {job.last_error}
        </p>
      ) : null}
      {!TERMINAL_STATES.has(job.state) ? (
        <div className="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            disabled={isActing}
            onClick={onCancel}
          >
            <X aria-hidden="true" />
            {isActing ? "Cancelling…" : "Cancel job"}
          </Button>
        </div>
      ) : null}
    </article>
  );
}

function CorpusImportCard({
  corpusImport,
  isActing,
  onCancel,
}: {
  corpusImport: CorpusImport;
  isActing: boolean;
  onCancel: () => void;
}) {
  const createdAt = formatKnowledgeDate(corpusImport.created_at);
  const startedAt = formatKnowledgeDate(corpusImport.started_at);
  const finishedAt = formatKnowledgeDate(corpusImport.finished_at);
  const skippedReport = parseSkippedReport(corpusImport.skipped);
  return (
    <article className="space-y-3 border p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-medium">
            {corpusImport.prefix === "" ? "Storage root" : corpusImport.prefix}
          </h4>
          <p className="mt-1 text-xs text-muted-foreground">
            {corpusImport.storage_provider} · revision{" "}
            {corpusImport.storage_provider_config_revision}
          </p>
        </div>
        <StateBadge state={corpusImport.state} />
      </div>
      <dl className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <CompactValue label="Attempts" value={String(corpusImport.attempts)} />
        <CompactValue
          label="Discovered"
          value={String(corpusImport.discovered_count)}
        />
        <CompactValue
          label="Queued"
          value={String(corpusImport.queued_count)}
        />
        <CompactValue label="Skipped" value={String(skippedReport.total)} />
        <CompactValue label="Filed" value={createdAt.label} />
        <CompactValue label="Started" value={startedAt.label} />
        <CompactValue label="Finished" value={finishedAt.label} />
        <CompactValue label="Import ID" value={corpusImport.id} code />
      </dl>
      {skippedReport.entries.length > 0 ? (
        <details className="border p-3 text-xs">
          <summary className="cursor-pointer font-medium">
            Skipped objects ({skippedReport.total})
          </summary>
          <ul className="mt-3 max-h-40 space-y-2 overflow-y-auto text-muted-foreground">
            {skippedReport.entries.map((entry, index) => (
              <li key={`${entry.key}:${index}`} className="break-words">
                <span className="font-mono text-foreground">{entry.key}</span>
                {" — "}
                {entry.reason}
              </li>
            ))}
          </ul>
          {skippedReport.total > skippedReport.entries.length ? (
            <p className="mt-2 text-muted-foreground">
              Showing the first {skippedReport.entries.length} reported objects.
            </p>
          ) : null}
        </details>
      ) : null}
      {corpusImport.last_error !== null ? (
        <p className="border border-destructive/30 bg-destructive/5 p-3 text-xs leading-5 text-destructive">
          {corpusImport.last_error}
        </p>
      ) : null}
      {!TERMINAL_STATES.has(corpusImport.state) ? (
        <div className="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            disabled={isActing}
            onClick={onCancel}
          >
            <X aria-hidden="true" />
            {isActing ? "Cancelling…" : "Cancel sweep"}
          </Button>
        </div>
      ) : null}
    </article>
  );
}

function WorkSection({
  children,
  empty,
  title,
}: {
  children: ReactNode[];
  empty: string;
  title: string;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
          {title}
        </h3>
        <span className="text-xs text-muted-foreground">{children.length}</span>
      </div>
      {children.length === 0 ? (
        <p className="border py-8 text-center text-sm text-muted-foreground">
          {empty}
        </p>
      ) : (
        <div className="space-y-3">{children}</div>
      )}
    </section>
  );
}

function StateBadge({ state }: { state: KnowledgeDurableState }) {
  return (
    <Badge variant={state === "failed" ? "destructive" : "outline"}>
      {state.charAt(0).toUpperCase() + state.slice(1)}
    </Badge>
  );
}

function CompactValue({
  code = false,
  label,
  value,
}: {
  code?: boolean;
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn("mt-1 truncate", code && "font-mono")} title={value}>
        {value}
      </dd>
    </div>
  );
}

function Field({
  children,
  hint,
  htmlFor,
  label,
  optional = false,
}: {
  children: ReactNode;
  hint?: string;
  htmlFor: string;
  label: string;
  optional?: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>
        {label}
        {optional ? (
          <span className="font-normal text-muted-foreground"> · Optional</span>
        ) : (
          <span aria-hidden="true"> *</span>
        )}
      </Label>
      {children}
      {hint !== undefined ? (
        <p className="text-xs leading-5 text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

function DialogMessage({
  draftError,
  error,
  hasDraft,
  onDiscard,
  savedAt,
}: {
  draftError: string | null;
  error: string | null;
  hasDraft: boolean;
  onDiscard: () => void;
  savedAt: string | null;
}) {
  return (
    <div className="space-y-2">
      {draftError !== null ? (
        <p
          className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
          role="alert"
        >
          {draftError}
        </p>
      ) : null}
      {error !== null ? (
        <p
          className="border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
          role="alert"
        >
          {error}
        </p>
      ) : null}
      {hasDraft && savedAt !== null ? (
        <div className="flex items-center justify-between gap-3 border bg-muted/30 p-3">
          <p className="text-xs text-muted-foreground">
            Draft saved locally {formatKnowledgeDate(savedAt).label}
          </p>
          <Button type="button" variant="ghost" size="sm" onClick={onDiscard}>
            Discard
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function DraftMarker() {
  return (
    <span
      className="size-1.5 rounded-full bg-current"
      aria-label="Draft saved"
    />
  );
}

function ContentSkeleton() {
  return (
    <div className="space-y-6" aria-label="Loading Knowledge work">
      {[0, 1].map((section) => (
        <div key={section} className="space-y-3">
          <Skeleton className="h-3 w-28" />
          {[0, 1].map((row) => (
            <div key={row} className="space-y-3 border p-4">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

interface SkippedEntry {
  key: string;
  reason: string;
}

function parseSkippedReport(value: CorpusImport["skipped"]): {
  entries: SkippedEntry[];
  total: number;
} {
  if (!isRecord(value)) {
    return { entries: [], total: 0 };
  }
  const entries = Array.isArray(value.entries)
    ? value.entries.flatMap((entry) => {
        if (
          !isRecord(entry) ||
          typeof entry.key !== "string" ||
          typeof entry.reason !== "string"
        ) {
          return [];
        }
        return [
          {
            key: entry.key.slice(0, 1_024),
            reason: entry.reason.slice(0, 512),
          },
        ];
      })
    : [];
  const reportedTotal =
    typeof value.total === "number" &&
    Number.isSafeInteger(value.total) &&
    value.total >= 0
      ? value.total
      : entries.length;
  return { entries, total: Math.max(reportedTotal, entries.length) };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export { KnowledgeContentPanel };
