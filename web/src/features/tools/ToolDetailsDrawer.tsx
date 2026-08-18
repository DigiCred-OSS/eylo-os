import { Ban, CircleStop, Rocket, Trash2, X } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useState, type ReactNode } from "react";

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
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  formatToolDate,
  formatToolEnum,
} from "@/features/tools/tool-formatters";
import type { ToolRecord, ToolSource } from "@/features/tools/tools.types";

interface ToolDetailsDrawerProps {
  onClose: () => void;
  organizationId: string;
  source: ToolSource;
  toolId: string | undefined;
}

const ToolDetailsDrawer = observer(function ToolDetailsDrawer({
  onClose,
  organizationId,
  source,
  toolId,
}: ToolDetailsDrawerProps) {
  const { tools } = useRootStore();
  const [confirmation, setConfirmation] = useState<"delete" | "revoke" | null>(
    null,
  );
  const [reason, setReason] = useState("");
  const tool = tools.selectedTool;

  async function confirmAction(): Promise<void> {
    if (confirmation === "delete") {
      if (await tools.deleteSelected(organizationId)) {
        setConfirmation(null);
        onClose();
      }
      return;
    }
    if (confirmation === "revoke" && reason.trim() !== "") {
      if (await tools.revoke(organizationId, reason.trim())) {
        setConfirmation(null);
        setReason("");
      }
    }
  }

  return (
    <>
      <Drawer
        open={toolId !== undefined}
        onOpenChange={(open) => {
          if (!open) onClose();
        }}
        swipeDirection="right"
      >
        <DrawerContent className="[--drawer-content-width:min(100%,42rem)]">
          <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
            <DrawerTitle>{tool?.displayName ?? "Tool details"}</DrawerTitle>
            <DrawerDescription>
              Agent-facing contract, execution boundary, and lifecycle
              authority.
            </DrawerDescription>
          </DrawerHeader>
          <Button
            className="absolute top-4 right-4 z-20"
            variant="ghost"
            size="icon"
            aria-label="Close tool details"
            title="Close"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </Button>
          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {tools.isSelectedLoading && tool === null ? (
              <ToolDetailsSkeleton />
            ) : tools.selectedErrorMessage !== null ? (
              <div
                className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
                role="alert"
              >
                {tools.selectedErrorMessage}
              </div>
            ) : tool !== null ? (
              <ToolDetails tool={tool} source={source} />
            ) : null}
            {tools.actionErrorMessage !== null ? (
              <div
                className="mt-4 border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive"
                role="alert"
              >
                {tools.actionErrorMessage}
              </div>
            ) : null}
          </div>
          {tool !== null && source === "managed" ? (
            <DrawerFooter className="flex-row flex-wrap border-t p-4">
              {tool.lifecycle === "draft" ? (
                <Button
                  disabled={tools.isActing}
                  onClick={() => void tools.publish(organizationId)}
                >
                  <Rocket aria-hidden="true" />
                  {tools.isActing ? "Publishing…" : "Publish"}
                </Button>
              ) : null}
              {tool.lifecycle === "published" ? (
                <Button
                  variant="outline"
                  disabled={tools.isActing}
                  onClick={() => void tools.withdraw(organizationId)}
                >
                  <CircleStop aria-hidden="true" />
                  {tools.isActing ? "Withdrawing…" : "Withdraw"}
                </Button>
              ) : null}
              {tool.publishedRevision !== null &&
              tool.publishedRevision !== undefined ? (
                <Button
                  variant="outline"
                  disabled={tools.isActing}
                  onClick={() => setConfirmation("revoke")}
                >
                  <Ban aria-hidden="true" />
                  Revoke revision
                </Button>
              ) : (
                <Button
                  variant="destructive"
                  disabled={tools.isActing}
                  onClick={() => setConfirmation("delete")}
                >
                  <Trash2 aria-hidden="true" />
                  Delete draft
                </Button>
              )}
            </DrawerFooter>
          ) : null}
        </DrawerContent>
      </Drawer>

      <Dialog
        open={confirmation !== null}
        onOpenChange={(open) => {
          if (!open && !tools.isActing) {
            setConfirmation(null);
            setReason("");
          }
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>
              {confirmation === "delete"
                ? "Delete draft tool?"
                : "Revoke published revision?"}
            </DialogTitle>
            <DialogDescription>
              {confirmation === "delete"
                ? "This removes the unpublished definition. The action cannot be undone."
                : "Revocation prevents new use of this exact revision and keeps its audit history."}
            </DialogDescription>
          </DialogHeader>
          {confirmation === "delete" ? (
            <div className="space-y-2">
              <Label htmlFor="delete-tool-confirmation">Tool name</Label>
              <Input
                id="delete-tool-confirmation"
                autoComplete="off"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Type {tool?.displayName ?? "the tool name"} to confirm.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="revoke-tool-reason">Reason</Label>
              <Input
                id="revoke-tool-reason"
                maxLength={2000}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              disabled={tools.isActing}
              onClick={() => setConfirmation(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={
                tools.isActing ||
                (confirmation === "delete"
                  ? reason !== tool?.displayName
                  : reason.trim() === "")
              }
              onClick={() => void confirmAction()}
            >
              {tools.isActing
                ? "Working…"
                : confirmation === "delete"
                  ? "Delete tool"
                  : "Revoke revision"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
});

function ToolDetails({
  tool,
  source,
}: {
  tool: ToolRecord;
  source: ToolSource;
}) {
  const updated = formatToolDate(tool.updatedAt);
  const inputSchema = tool.llmConfig?.inputSchema;
  return (
    <div className="space-y-8">
      <DetailsSection title="Overview">
        <DetailRow label="Source">{formatToolEnum(source)}</DetailRow>
        <DetailRow label="Kind">
          <Badge variant="outline">{formatToolEnum(tool.kind)}</Badge>
        </DetailRow>
        <DetailRow label={source === "managed" ? "Lifecycle" : "Availability"}>
          <Badge variant="outline">
            {source === "managed"
              ? formatToolEnum(tool.lifecycle)
              : "Available"}
          </Badge>
        </DetailRow>
        <DetailRow label="Execution">
          <Badge variant="outline">{formatToolEnum(tool.executionMode)}</Badge>
        </DetailRow>
        <DetailRow label="Updated">
          {source !== "managed" ? (
            "Code-owned catalog"
          ) : tool.updatedAt === undefined ? (
            updated.label
          ) : (
            <time dateTime={tool.updatedAt} title={updated.title}>
              {updated.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="Tool ID">
          <code className="break-all text-xs">{tool.id}</code>
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Agent contract">
        <DetailRow label="Callable name">
          <code className="break-all text-xs">{tool.name}</code>
        </DetailRow>
        <DetailRow label="Description">
          <span className="break-words">
            {tool.description || "No description"}
          </span>
        </DetailRow>
        <DetailRow label="Input fields">
          {inputSchema === undefined ||
          Object.keys(inputSchema.properties ?? {}).length === 0
            ? "No inputs"
            : Object.keys(inputSchema.properties ?? {}).join(", ")}
        </DetailRow>
        <DetailRow label="Required inputs">
          {inputSchema?.required?.join(", ") || "None"}
        </DetailRow>
      </DetailsSection>
      {source === "managed" ? (
        <DetailsSection title="Revision">
          <DetailRow label="Draft version">{tool.draftVersion}</DetailRow>
          <DetailRow label="Draft changed">
            {tool.draftDirty ? "Yes" : "No"}
          </DetailRow>
          <DetailRow label="Published revision">
            {tool.publishedRevision ?? "Not published"}
          </DetailRow>
        </DetailsSection>
      ) : null}
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
    <div className="grid gap-1 py-3 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm">{children}</dd>
    </div>
  );
}

function ToolDetailsSkeleton() {
  return (
    <div className="space-y-5">
      {Array.from({ length: 6 }, (_, index) => (
        <Skeleton key={index} className="h-10 w-full" />
      ))}
    </div>
  );
}

export { ToolDetailsDrawer };
