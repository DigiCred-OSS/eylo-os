import { Bot, Pencil, X } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useState, type ReactNode } from "react";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Skeleton } from "@/components/ui/skeleton";
import { KnowledgeContentPanel } from "@/features/knowledge/KnowledgeContentPanel";
import { KnowledgeAgentAccessDialog } from "@/features/knowledge/KnowledgeAgentAccessDialog";
import { KnowledgeReindexPanel } from "@/features/knowledge/KnowledgeReindexPanel";
import {
  formatChunkingStrategy,
  formatKnowledgeDate,
  formatKnowledgeScope,
  formatKnowledgeVendor,
} from "@/features/knowledge/knowledge-formatters";
import type { Knowledgebase } from "@/features/knowledge/knowledge.types";

interface KnowledgeDetailsDrawerProps {
  activeView: "content" | "overview";
  knowledgebaseId: string | undefined;
  memberKey: string | null;
  organizationId: string;
  returnTo: string;
  onClose: () => void;
  onEdit: (knowledgebaseId: string) => void;
  onViewChange: (view: "content" | "overview") => void;
}

const KnowledgeDetailsDrawer = observer(function KnowledgeDetailsDrawer({
  activeView,
  knowledgebaseId,
  memberKey,
  organizationId,
  returnTo,
  onClose,
  onEdit,
  onViewChange,
}: KnowledgeDetailsDrawerProps) {
  const { knowledge } = useRootStore();
  const knowledgebase = knowledge.selectedKnowledgebase;
  const [accessDialogOpen, setAccessDialogOpen] = useState(false);

  useEffect(() => {
    setAccessDialogOpen(false);
  }, [knowledgebaseId]);

  return (
    <Drawer
      open={knowledgebaseId !== undefined}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
      swipeDirection="right"
    >
      <DrawerContent className="[--drawer-content-width:min(100%,44rem)]">
        <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
          <DrawerTitle>
            {knowledgebase?.name ?? "Knowledgebase details"}
          </DrawerTitle>
          <DrawerDescription>
            {activeView === "overview"
              ? "Retrieval, scope, write behavior, and pinned provider authority."
              : "File content and inspect durable ingestion state."}
          </DrawerDescription>
          <div
            className="mt-3 flex gap-1"
            role="tablist"
            aria-label="Knowledgebase details"
          >
            <Button
              role="tab"
              aria-selected={activeView === "overview"}
              size="sm"
              variant={activeView === "overview" ? "secondary" : "ghost"}
              onClick={() => onViewChange("overview")}
            >
              Overview
            </Button>
            <Button
              role="tab"
              aria-selected={activeView === "content"}
              size="sm"
              variant={activeView === "content" ? "secondary" : "ghost"}
              onClick={() => onViewChange("content")}
            >
              Content
            </Button>
          </div>
        </DrawerHeader>
        <Button
          className="absolute top-4 right-4 z-20"
          variant="ghost"
          size="icon"
          aria-label="Close knowledgebase details"
          title="Close"
          onClick={onClose}
        >
          <X aria-hidden="true" />
        </Button>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {knowledge.isSelectedLoading && knowledgebase === null ? (
            <KnowledgeDetailsSkeleton />
          ) : knowledge.selectedErrorMessage !== null ? (
            <div
              className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
              role="alert"
            >
              {knowledge.selectedErrorMessage}
            </div>
          ) : knowledgebase !== null ? (
            activeView === "overview" ? (
              <KnowledgeDetails
                knowledgebase={knowledgebase}
                organizationId={organizationId}
              />
            ) : memberKey !== null && knowledgebaseId !== undefined ? (
              <KnowledgeContentPanel
                knowledgebaseId={knowledgebaseId}
                memberKey={memberKey}
                organizationId={organizationId}
                returnTo={returnTo}
              />
            ) : null
          ) : null}
        </div>

        {knowledgebase === null || activeView !== "overview" ? null : (
          <DrawerFooter className="border-t p-4 sm:flex-row">
            <Button
              className="w-full sm:w-auto sm:flex-1"
              variant="outline"
              onClick={() => setAccessDialogOpen(true)}
            >
              <Bot aria-hidden="true" />
              Configure Agent access
            </Button>
            <Button
              className="w-full sm:w-auto sm:flex-1"
              onClick={() => onEdit(knowledgebase.id)}
            >
              <Pencil aria-hidden="true" />
              Edit knowledgebase
            </Button>
          </DrawerFooter>
        )}

        {knowledgebase === null ? null : (
          <KnowledgeAgentAccessDialog
            knowledgebaseName={knowledgebase.name}
            open={accessDialogOpen}
            organizationId={organizationId}
            returnTo={returnTo}
            writable={knowledgebase.writable}
            onOpenChange={setAccessDialogOpen}
          />
        )}
      </DrawerContent>
    </Drawer>
  );
});

function KnowledgeDetails({
  knowledgebase,
  organizationId,
}: {
  knowledgebase: Knowledgebase;
  organizationId: string;
}) {
  const createdAt = formatKnowledgeDate(knowledgebase.created_at);
  const updatedAt = formatKnowledgeDate(knowledgebase.updated_at);
  const metadata = knowledgebase.metadata;

  return (
    <div className="space-y-8">
      <DetailsSection title="Overview">
        <DetailRow label="Search method">
          <Badge variant="outline">
            {formatKnowledgeVendor(knowledgebase.vendor)}
          </Badge>
        </DetailRow>
        <DetailRow label="Scope">
          <Badge variant="outline">
            {formatKnowledgeScope(knowledgebase.scope)}
          </Badge>
        </DetailRow>
        <DetailRow label="Scope ID">
          <CodeValue>{knowledgebase.scope_id}</CodeValue>
        </DetailRow>
        <DetailRow label="Agent writes">
          <Badge variant="outline">
            {knowledgebase.writable
              ? "Accepted by explicit grant"
              : "Read-only"}
          </Badge>
        </DetailRow>
      </DetailsSection>

      <DetailsSection title="Chunking">
        <DetailRow label="Strategy">
          {metadata === null ? (
            "Not recorded"
          ) : (
            <Badge variant="outline">
              {formatChunkingStrategy(metadata.chunking)}
            </Badge>
          )}
        </DetailRow>
        <DetailRow label="Chunk size">
          {metadata === null
            ? "Not recorded"
            : `${metadata.chunk_size} characters`}
        </DetailRow>
        <DetailRow label="Overlap">
          {metadata === null
            ? "Not recorded"
            : `${metadata.chunk_overlap} characters`}
        </DetailRow>
      </DetailsSection>

      {knowledgebase.vendor === "pgvector" ? (
        <>
          <DetailsSection title="Embedding authority">
            <DetailRow label="Provider">
              {knowledgebase.embedding_provider ?? "Not recorded"}
            </DetailRow>
            <DetailRow label="Model">
              {knowledgebase.embedding_model ?? "Not recorded"}
            </DetailRow>
            <DetailRow label="Dimensions">
              {knowledgebase.embedding_dimensions ?? "Not recorded"}
            </DetailRow>
            <DetailRow label="Config revision">
              {knowledgebase.embedding_provider_config_revision ??
                "Not recorded"}
            </DetailRow>
            <DetailRow label="Config ID">
              <CodeValue>
                {knowledgebase.embedding_provider_config_id ?? "Not recorded"}
              </CodeValue>
            </DetailRow>
          </DetailsSection>
          <KnowledgeReindexPanel
            key={knowledgebase.id}
            knowledgebase={knowledgebase}
            organizationId={organizationId}
          />
        </>
      ) : null}

      <DetailsSection title="Record">
        <DetailRow label="Created">
          <DateValue value={createdAt} />
        </DetailRow>
        <DetailRow label="Updated">
          <DateValue value={updatedAt} />
        </DetailRow>
        <DetailRow label="Knowledgebase ID">
          <CodeValue>{knowledgebase.id}</CodeValue>
        </DetailRow>
      </DetailsSection>
    </div>
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
    <section className="space-y-3">
      <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
      </h2>
      <dl className="divide-y border-y">{children}</dl>
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
    <div className="grid gap-1 py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm leading-5">{children}</dd>
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

function KnowledgeDetailsSkeleton() {
  return (
    <div className="space-y-8" aria-label="Loading knowledgebase details">
      {[0, 1, 2].map((section) => (
        <div key={section} className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <div className="space-y-px border-y">
            {[0, 1, 2].map((row) => (
              <div key={row} className="grid grid-cols-[11rem_1fr] gap-4 py-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-full" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export { KnowledgeDetailsDrawer };
