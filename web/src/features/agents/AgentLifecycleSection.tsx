import { ArchiveX, Send, ShieldAlert, Trash2 } from "lucide-react";
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
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { AgentStatusBadge } from "@/features/agents/AgentStatusBadge";
import { AgentDeleteDialog } from "@/features/agents/AgentDeleteDialog";
import { formatAgentEnum } from "@/features/agents/agent-formatters";
import { useAsyncContextGuard } from "@/lib/use-async-context-guard";

interface AgentLifecycleSectionProps {
  agentId: string;
  onDeleted: () => void;
  organizationId: string;
}

const AgentLifecycleSection = observer(function AgentLifecycleSection({
  agentId,
  onDeleted,
  organizationId,
}: AgentLifecycleSectionProps) {
  const { agents } = useRootStore();
  const form = agents.form;
  const lifecycle = agents.lifecycle;
  const agent = form.serverAgent;
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [revokeReason, setRevokeReason] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const contextKey = `${organizationId}:${agentId}`;
  const isCurrentContext = useAsyncContextGuard(contextKey);

  useEffect(() => {
    lifecycle.clearMessages();
  }, [agentId, lifecycle]);

  if (agent === null) {
    return null;
  }

  const hasUnsavedForm = form.isDirty || form.conflictMessage !== null;
  const lifecycleDisabled =
    lifecycle.isActing || agents.isDeleting || hasUnsavedForm;
  const canDelete = agent.publishedRevision == null;

  return (
    <div className="space-y-5">
      {hasUnsavedForm ? (
        <div
          className="border border-warning/40 bg-warning/5 p-4 text-sm"
          role="status"
        >
          Save or discard the local form draft before changing lifecycle state.
        </div>
      ) : null}
      {lifecycle.errorMessage !== null ? (
        <div
          className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          role="alert"
        >
          {lifecycle.errorMessage}
        </div>
      ) : null}
      {lifecycle.noticeMessage !== null ? (
        <div
          className="border border-success/30 bg-success/5 p-4 text-sm text-success"
          role="status"
        >
          {lifecycle.noticeMessage}
        </div>
      ) : null}

      <LifecycleCard
        title="Publication"
        description="Publish one immutable revision for new work, or withdraw the stable alias."
      >
        <dl className="grid gap-4 sm:grid-cols-2">
          <LifecycleValue label="Status">
            <AgentStatusBadge status={agent.status} />
          </LifecycleValue>
          <LifecycleValue label="Definition state">
            <Badge variant="outline">{formatAgentEnum(agent.lifecycle)}</Badge>
          </LifecycleValue>
          <LifecycleValue label="Draft version">
            {agent.draftVersion}
          </LifecycleValue>
          <LifecycleValue label="Published revision">
            {agent.publishedRevision ?? "Not published"}
          </LifecycleValue>
        </dl>

        <div className="mt-5 flex flex-wrap gap-2">
          {agent.draftDirty ? (
            <Button
              type="button"
              disabled={lifecycleDisabled}
              onClick={() => void lifecycle.publish(organizationId, agentId)}
            >
              <Send aria-hidden="true" />
              {agent.publishedRevision == null
                ? "Publish Agent"
                : "Publish changes"}
            </Button>
          ) : null}
          {agent.lifecycle === "published" ? (
            <Button
              type="button"
              variant="outline"
              disabled={lifecycleDisabled}
              onClick={() => void lifecycle.withdraw(organizationId, agentId)}
            >
              <ArchiveX aria-hidden="true" />
              Withdraw
            </Button>
          ) : null}
        </div>
      </LifecycleCard>

      {agent.publishedRevision != null ? (
        <LifecycleCard
          title="Emergency revocation"
          description="Block one exact revision, including pinned resume, and request cancellation of affected runs."
        >
          <Button
            type="button"
            variant="destructive"
            disabled={lifecycleDisabled}
            onClick={() => {
              setRevokeReason("");
              setRevokeOpen(true);
            }}
          >
            <ShieldAlert aria-hidden="true" />
            Revoke revision {agent.publishedRevision}
          </Button>
        </LifecycleCard>
      ) : null}

      <LifecycleCard
        title="Delete Agent"
        description="Delete a draft-only Agent from the organization collection."
      >
        {canDelete ? (
          <Button
            type="button"
            variant="destructive"
            disabled={lifecycleDisabled}
            onClick={() => {
              agents.clearDeleteError();
              setDeleteOpen(true);
            }}
          >
            <Trash2 aria-hidden="true" />
            Delete Agent
          </Button>
        ) : (
          <p className="text-sm leading-5 text-muted-foreground">
            This Agent has published revisions. The current API retains its
            definition for audit and durable-run references; use Withdraw or
            emergency Revocation instead.
          </p>
        )}
      </LifecycleCard>

      <Dialog open={revokeOpen} onOpenChange={setRevokeOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>Revoke revision {agent.publishedRevision}</DialogTitle>
            <DialogDescription>
              Emergency action. Existing pinned work can no longer resume this
              revision. State the audit reason.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="revoke-reason">Reason</Label>
            <Textarea
              id="revoke-reason"
              required
              maxLength={2000}
              value={revokeReason}
              onChange={(event) => setRevokeReason(event.target.value)}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setRevokeOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={revokeReason.trim() === "" || lifecycle.isActing}
              onClick={async () => {
                const revision = agent.publishedRevision;
                if (revision == null) return;
                const revoked = await lifecycle.revoke(
                  organizationId,
                  agentId,
                  revision,
                  revokeReason,
                );
                if (revoked) setRevokeOpen(false);
              }}
            >
              Revoke revision
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AgentDeleteDialog
        agent={agent}
        errorMessage={agents.deleteErrorMessage}
        isDeleting={agents.isDeleting}
        open={deleteOpen}
        onOpenChange={(open) => {
          setDeleteOpen(open);
          if (!open) agents.clearDeleteError();
        }}
        onConfirm={async () => {
          const submittedContextKey = contextKey;
          const deleted = await agents.deleteAgent(organizationId, agentId);
          if (deleted && isCurrentContext(submittedContextKey)) {
            setDeleteOpen(false);
            onDeleted();
            return true;
          }
          return false;
        }}
      />
    </div>
  );
});

function LifecycleCard({
  children,
  description,
  title,
}: {
  children: React.ReactNode;
  description: string;
  title: string;
}) {
  return (
    <section className="border bg-card">
      <div className="space-y-1 p-5">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm leading-5 text-muted-foreground">{description}</p>
      </div>
      <Separator />
      <div className="p-5">{children}</div>
    </section>
  );
}

function LifecycleValue({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm font-medium">{children}</dd>
    </div>
  );
}

export { AgentLifecycleSection };
