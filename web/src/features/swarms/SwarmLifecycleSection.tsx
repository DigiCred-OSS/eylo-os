import { ShieldAlert } from "lucide-react";
import { useState } from "react";

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
import { Textarea } from "@/components/ui/textarea";
import { SwarmLifecycleBadge } from "@/features/swarms/SwarmLifecycleBadge";
import type { Swarm, SwarmMemberView } from "@/features/swarms/swarms.types";

interface SwarmLifecycleSectionProps {
  activeAction: string | null;
  hasUnsavedDetails: boolean;
  members: readonly SwarmMemberView[];
  onPublish: () => Promise<boolean>;
  onRevoke: (reason: string) => Promise<boolean>;
  onWithdraw: () => Promise<boolean>;
  swarm: Swarm;
}

function SwarmLifecycleSection({
  activeAction,
  hasUnsavedDetails,
  members,
  onPublish,
  onRevoke,
  onWithdraw,
  swarm,
}: SwarmLifecycleSectionProps) {
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [reason, setReason] = useState("");
  const hasUnavailableMember = members.some(
    ({ agent }) =>
      agent === null ||
      agent.lifecycle !== "published" ||
      agent.publishedRevision == null,
  );
  const publishBlocked =
    hasUnsavedDetails ||
    !swarm.draftDirty ||
    members.length === 0 ||
    hasUnavailableMember ||
    activeAction !== null;

  function changeRevokeOpen(open: boolean): void {
    if (!open && activeAction === "revoke") return;
    if (!open) setReason("");
    setRevokeOpen(open);
  }

  async function revoke(): Promise<void> {
    if (reason.trim() === "") return;
    if (await onRevoke(reason)) changeRevokeOpen(false);
  }

  return (
    <section className="grid gap-5 border p-4 sm:p-5 lg:grid-cols-[14rem_minmax(0,1fr)]">
      <div>
        <h2 className="text-base font-medium">Lifecycle</h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          Publish one immutable topology for new work. Withdrawal stops new
          selection; emergency revocation also stops pinned resumes.
        </p>
      </div>
      <div className="min-w-0 space-y-5">
        <dl className="divide-y border-y">
          <DetailRow label="Lifecycle">
            <SwarmLifecycleBadge lifecycle={swarm.lifecycle} />
          </DetailRow>
          <DetailRow label="Draft state">
            <Badge variant="outline">
              {swarm.draftDirty ? "Changes pending" : "Current"}
            </Badge>
          </DetailRow>
          <DetailRow label="Draft version">{swarm.draftVersion}</DetailRow>
          <DetailRow label="Published revision">
            {swarm.publishedRevision ?? "Not published"}
          </DetailRow>
        </dl>
        {hasUnsavedDetails ? (
          <p className="text-sm text-muted-foreground">
            Save the Swarm details before publishing so the intended name and
            description enter the immutable revision.
          </p>
        ) : members.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Add at least one Agent before publishing.
          </p>
        ) : hasUnavailableMember ? (
          <p className="text-sm text-muted-foreground">
            Every member Agent must be published and available for new work.
          </p>
        ) : !swarm.draftDirty ? (
          <p className="text-sm text-muted-foreground">
            This draft already matches the published revision. Change its
            details or topology before publishing another revision.
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            disabled={publishBlocked}
            onClick={() => void onPublish()}
          >
            {activeAction === "publish" ? "Publishing…" : "Publish topology"}
          </Button>
          {swarm.lifecycle === "published" ? (
            <Button
              type="button"
              variant="outline"
              disabled={activeAction !== null}
              onClick={() => void onWithdraw()}
            >
              {activeAction === "withdraw" ? "Withdrawing…" : "Withdraw"}
            </Button>
          ) : null}
          {swarm.publishedRevision != null ? (
            <Button
              type="button"
              variant="destructive"
              disabled={activeAction !== null}
              onClick={() => changeRevokeOpen(true)}
            >
              <ShieldAlert aria-hidden="true" />
              Revoke revision {swarm.publishedRevision}
            </Button>
          ) : null}
        </div>
      </div>

      <Dialog open={revokeOpen} onOpenChange={changeRevokeOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>
              Revoke Swarm revision {swarm.publishedRevision}?
            </DialogTitle>
            <DialogDescription>
              Emergency revocation prevents new selection and pinned resume,
              then requests cancellation of affected runs. This cannot be
              undone.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="swarm-revocation-reason">Reason</Label>
            <Textarea
              id="swarm-revocation-reason"
              maxLength={2_000}
              rows={4}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {reason.length.toLocaleString()} / 2,000
            </p>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={activeAction === "revoke"}
              onClick={() => changeRevokeOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={reason.trim() === "" || activeAction !== null}
              onClick={() => void revoke()}
            >
              {activeAction === "revoke" ? "Revoking…" : "Revoke revision"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function DetailRow({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm leading-5">{children}</dd>
    </div>
  );
}

export { SwarmLifecycleSection };
