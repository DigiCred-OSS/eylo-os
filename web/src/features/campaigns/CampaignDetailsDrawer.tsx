import {
  Ban,
  ExternalLink,
  MoreHorizontal,
  Pause,
  Pencil,
  Play,
  Plus,
  ShieldX,
  Trash2,
  X,
} from "lucide-react";
import { observer } from "mobx-react-lite";
import { useState, type ReactNode } from "react";
import { Link } from "react-router";

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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { CampaignAudienceDialog } from "@/features/campaigns/CampaignAudienceDialog";
import {
  campaignProgress,
  formatCampaignDate,
  formatCampaignEnum,
} from "@/features/campaigns/campaign-formatters";
import type {
  Campaign,
  CampaignAnalytics,
  CampaignContact,
  CampaignPreparation,
} from "@/features/campaigns/campaigns.types";

interface CampaignDetailsDrawerProps {
  campaignId: string | undefined;
  onClose: () => void;
  organizationId: string;
}

type Confirmation = "cancel" | "delete" | "pause" | "revoke" | null;

const CampaignDetailsDrawer = observer(function CampaignDetailsDrawer({
  campaignId,
  onClose,
  organizationId,
}: CampaignDetailsDrawerProps) {
  const { campaigns } = useRootStore();
  const campaign = campaigns.selectedCampaign;
  const [audienceOpen, setAudienceOpen] = useState(false);
  const [startOpen, setStartOpen] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation>(null);
  const [revokeReason, setRevokeReason] = useState("");

  const editable =
    campaign !== null && ["draft", "paused"].includes(campaign.status);
  const startable =
    campaign !== null &&
    ["draft", "paused", "scheduled"].includes(campaign.status);

  async function reviewStart(): Promise<void> {
    await campaigns.refreshPreparation(organizationId);
    setStartOpen(true);
  }

  async function confirmAction(): Promise<void> {
    if (confirmation === null) return;
    if (confirmation === "delete") {
      if (await campaigns.removeSelected(organizationId)) {
        setConfirmation(null);
        onClose();
      }
      return;
    }
    if (confirmation === "revoke") {
      if (revokeReason.trim() === "") return;
      if (await campaigns.revokeSelected(organizationId, revokeReason.trim())) {
        setConfirmation(null);
        setRevokeReason("");
      }
      return;
    }
    if (await campaigns.transition(organizationId, confirmation))
      setConfirmation(null);
  }

  return (
    <>
      <Drawer
        open={campaignId !== undefined}
        onOpenChange={(open) => {
          if (!open) onClose();
        }}
        swipeDirection="right"
      >
        <DrawerContent className="[--drawer-content-width:min(100%,58rem)]">
          <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
            <DrawerTitle>{campaign?.name ?? "Campaign"}</DrawerTitle>
            <DrawerDescription>
              Audience, exact definition authority, preparation warnings,
              execution progress, and channel outcomes.
            </DrawerDescription>
          </DrawerHeader>
          <Button
            className="absolute top-4 right-4 z-20"
            variant="ghost"
            size="icon"
            aria-label="Close campaign"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </Button>
          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {campaigns.isSelectedLoading && campaign === null ? (
              <DetailsSkeleton />
            ) : campaigns.selectedErrorMessage !== null ? (
              <ErrorBox>{campaigns.selectedErrorMessage}</ErrorBox>
            ) : campaign === null ? null : (
              <CampaignDetails
                analytics={campaigns.analytics}
                campaign={campaign}
                contacts={campaigns.contacts}
                preparation={campaigns.preparation}
                organizationId={organizationId}
                agentName={campaigns.agentName(campaign.agentId)}
                templateName={campaigns.templateName(
                  campaign.initialMessageTemplateId,
                )}
                emailConfigName={campaigns.emailConfigName(
                  readString(campaign.channelConfig.provider_config_id),
                )}
              />
            )}
            {campaigns.actionErrorMessage === null ? null : (
              <div className="mt-4">
                <ErrorBox>{campaigns.actionErrorMessage}</ErrorBox>
              </div>
            )}
          </div>
          {campaign === null ? null : (
            <DrawerFooter className="flex-row flex-wrap border-t p-4">
              {editable ? (
                <Button variant="outline" onClick={() => setAudienceOpen(true)}>
                  <Plus aria-hidden="true" />
                  Add recipients
                </Button>
              ) : null}
              {startable ? (
                <Button
                  disabled={campaigns.isPreparationLoading}
                  onClick={() => void reviewStart()}
                >
                  <Play aria-hidden="true" />
                  {campaign.status === "paused" ? "Resume" : "Start"}
                </Button>
              ) : null}
              {campaign.status === "running" ? (
                <Button
                  variant="outline"
                  onClick={() => setConfirmation("pause")}
                >
                  <Pause aria-hidden="true" />
                  Pause
                </Button>
              ) : null}
              {editable ? (
                <Button
                  nativeButton={false}
                  render={
                    <Link
                      to={`/org/${organizationId}/outbound/campaigns/${campaign.id}/edit`}
                    />
                  }
                  variant="outline"
                >
                  <Pencil aria-hidden="true" />
                  Edit
                </Button>
              ) : null}
              <CampaignMoreMenu
                campaign={campaign}
                onConfirm={setConfirmation}
              />
            </DrawerFooter>
          )}
        </DrawerContent>
      </Drawer>
      {campaign === null ? null : (
        <CampaignAudienceDialog
          campaign={campaign}
          open={audienceOpen}
          onOpenChange={setAudienceOpen}
          organizationId={organizationId}
        />
      )}
      {campaign === null ? null : (
        <StartCampaignDialog
          campaign={campaign}
          open={startOpen}
          onOpenChange={setStartOpen}
          organizationId={organizationId}
          preparation={campaigns.preparation}
        />
      )}
      <ConfirmationDialog
        confirmation={confirmation}
        isActing={campaigns.isActing}
        reason={revokeReason}
        onReasonChange={setRevokeReason}
        onOpenChange={(open) => {
          if (!open && !campaigns.isActing) {
            setConfirmation(null);
            setRevokeReason("");
          }
        }}
        onConfirm={() => void confirmAction()}
      />
    </>
  );
});

function CampaignDetails({
  agentName,
  analytics,
  campaign,
  contacts,
  emailConfigName,
  organizationId,
  preparation,
  templateName,
}: {
  agentName: string;
  analytics: CampaignAnalytics | null;
  campaign: Campaign;
  contacts: readonly CampaignContact[];
  emailConfigName: string;
  organizationId: string;
  preparation: CampaignPreparation | null;
  templateName: string;
}) {
  const progress = campaignProgress(
    campaign.completedContacts,
    campaign.failedContacts,
    campaign.totalContacts,
  );
  const created = formatCampaignDate(campaign.createdAt);
  const updated = formatCampaignDate(campaign.updatedAt);
  const started = formatCampaignDate(campaign.startedAt);
  const completed = formatCampaignDate(campaign.completedAt);
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant={campaign.status === "canceled" ? "destructive" : "outline"}
          >
            {formatCampaignEnum(campaign.status)}
          </Badge>
          <Badge variant="outline">
            {formatCampaignEnum(campaign.channel)}
          </Badge>
        </div>
        {campaign.description ? (
          <p className="whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground">
            {campaign.description}
          </p>
        ) : null}
        <div className="space-y-1">
          <div className="flex justify-between gap-3 text-xs text-muted-foreground">
            <span>Progress</span>
            <span>
              {progress.label} · {progress.percent}%
            </span>
          </div>
          <div
            className="h-2 overflow-hidden bg-muted"
            aria-label={`${progress.percent}% complete`}
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress.percent}
          >
            <div
              className="h-full bg-foreground"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
        </div>
      </section>
      {analytics === null ? null : (
        <section className="space-y-3">
          <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Outcome summary
          </h2>
          <div className="grid gap-px border bg-border sm:grid-cols-3">
            <Metric label="Pending" value={analytics.pending} />
            <Metric label="Completed" value={analytics.completed} />
            <Metric
              danger={analytics.failed > 0}
              label="Failed"
              value={analytics.failed}
            />
          </div>
          <dl className="divide-y border-y">
            <DetailRow label="Connect rate">
              {formatPercent(analytics.connectRate)}
            </DetailRow>
            <DetailRow label="Average duration">
              {analytics.avgDurationSeconds === null ||
              analytics.avgDurationSeconds === undefined
                ? "Not recorded"
                : `${Math.round(analytics.avgDurationSeconds)} sec`}
            </DetailRow>
            <DetailRow label="Retry / skipped">
              {analytics.retry} / {analytics.skipped}
            </DetailRow>
          </dl>
          {Object.keys(analytics.outcomeDistribution).length === 0 ? null : (
            <div className="flex flex-wrap gap-2">
              {Object.entries(analytics.outcomeDistribution)
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([outcome, count]) => (
                  <Badge
                    key={outcome}
                    variant={
                      outcome.startsWith("error") ? "destructive" : "outline"
                    }
                  >
                    {formatCampaignEnum(outcome)} · {count}
                  </Badge>
                ))}
            </div>
          )}
        </section>
      )}
      <DetailsSection title="Definition">
        <DetailRow label="Agent">
          <Link
            className="underline underline-offset-4"
            to={`/org/${organizationId}/agents/${campaign.agentId}`}
          >
            {agentName} · revision {campaign.agentRevision}
          </Link>
        </DetailRow>
        <DetailRow label="Campaign revision">
          Published {campaign.publishedRevision}
          {campaign.activeRevision === null ||
          campaign.activeRevision === undefined
            ? " · inactive"
            : ` · active ${campaign.activeRevision}`}
        </DetailRow>
        <DetailRow label="Initial message">
          {campaign.initialMessageTemplateId === null ||
          campaign.initialMessageTemplateId === undefined ? (
            templateName
          ) : (
            <span>
              {templateName} · revision{" "}
              {campaign.initialMessageTemplateRevision}
            </span>
          )}
        </DetailRow>
        <DetailRow label="Concurrency">{campaign.concurrencyLimit}</DetailRow>
      </DetailsSection>
      <ChannelSection
        campaign={campaign}
        emailConfigName={emailConfigName}
        organizationId={organizationId}
      />
      <PreparationSection preparation={preparation} />
      <section className="space-y-3">
        <div>
          <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Recipients
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            First 100 filed campaign recipients. No policy-based recipient
            filtering occurs in V1.
          </p>
        </div>
        {contacts.length === 0 ? (
          <div className="border py-8 text-center text-sm text-muted-foreground">
            No recipients
          </div>
        ) : (
          <div className="divide-y border">
            {contacts.map((contact) => (
              <article
                className="grid gap-2 p-3 sm:grid-cols-[minmax(0,1fr)_8rem_6rem] sm:items-center"
                key={contact.id}
              >
                <div className="min-w-0">
                  <p className="break-all text-sm font-medium">
                    {contact.contactAddress || "No channel address"}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {contact.lastOutcomeReason ??
                      `Recipient …${contact.id.slice(-8)}`}
                  </p>
                </div>
                <Badge
                  variant={
                    contact.status === "failed" ? "destructive" : "outline"
                  }
                >
                  {formatCampaignEnum(contact.status)}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {contact.attemptCount} attempts
                </span>
              </article>
            ))}
          </div>
        )}
      </section>
      <DetailsSection title="Timing">
        <DetailRow label="Created">
          <time dateTime={campaign.createdAt} title={created.title}>
            {created.label}
          </time>
        </DetailRow>
        <DetailRow label="Updated">
          <time dateTime={campaign.updatedAt} title={updated.title}>
            {updated.label}
          </time>
        </DetailRow>
        <DetailRow label="Started">
          {campaign.startedAt === null || campaign.startedAt === undefined ? (
            started.label
          ) : (
            <time dateTime={campaign.startedAt} title={started.title}>
              {started.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="Completed">
          {campaign.completedAt === null ||
          campaign.completedAt === undefined ? (
            completed.label
          ) : (
            <time dateTime={campaign.completedAt} title={completed.title}>
              {completed.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="ID">
          <code className="break-all text-xs">{campaign.id}</code>
        </DetailRow>
      </DetailsSection>
    </div>
  );
}

function ChannelSection({
  campaign,
  emailConfigName,
  organizationId,
}: {
  campaign: Campaign;
  emailConfigName: string;
  organizationId: string;
}) {
  const config = campaign.channelConfig;
  return (
    <DetailsSection title="Channel and retry">
      <DetailRow label="Channel">
        <Badge variant="outline">{formatCampaignEnum(campaign.channel)}</Badge>
      </DetailRow>
      {campaign.channel === "email" ? (
        <>
          <DetailRow label="Email config">
            <Link
              className="inline-flex items-center gap-1 underline underline-offset-4"
              to={`/org/${organizationId}/providers/email/${readString(config.provider_config_id)}`}
            >
              {emailConfigName} · revision{" "}
              {readString(config.provider_config_revision)}
              <ExternalLink className="size-3.5" aria-hidden="true" />
            </Link>
          </DetailRow>
          <DetailRow label="Subject">
            <span className="whitespace-pre-wrap">
              {readString(config.subject_template) || "Not configured"}
            </span>
          </DetailRow>
          <DetailRow label="Body">
            <span className="whitespace-pre-wrap break-words">
              {readString(config.body_template) || "Not configured"}
            </span>
          </DetailRow>
        </>
      ) : null}
      <DetailRow label="Maximum retries">
        {readString(campaign.retryPolicy.max_retries) || "0"}
      </DetailRow>
      <DetailRow label="Backoff seconds">
        {readString(campaign.retryPolicy.backoff_seconds) || "0"}
      </DetailRow>
      <DetailRow label="Retry outcomes">
        {Array.isArray(campaign.retryPolicy.retry_on)
          ? campaign.retryPolicy.retry_on
              .filter((item): item is string => typeof item === "string")
              .map(formatCampaignEnum)
              .join(", ") || "None"
          : "None"}
      </DetailRow>
    </DetailsSection>
  );
}

function PreparationSection({
  preparation,
}: {
  preparation: CampaignPreparation | null;
}) {
  if (preparation === null) return null;
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Preparation
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Warnings describe the filed audience; they do not conditionally
            suppress contacts.
          </p>
        </div>
        <Badge
          variant={preparation.blockingFacts > 0 ? "destructive" : "outline"}
        >
          {preparation.selectedContacts} selected · {preparation.warningFacts}{" "}
          warnings
        </Badge>
      </div>
      {preparation.issues.length === 0 ? (
        <div className="border py-8 text-center text-sm text-muted-foreground">
          No preparation issues
        </div>
      ) : (
        <div className="divide-y border">
          {preparation.issues.map((issue) => (
            <article className="p-3" key={issue.code}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-medium">
                  {formatCampaignEnum(issue.code)}
                </p>
                <Badge
                  variant={
                    issue.level === "blocker" ? "destructive" : "outline"
                  }
                >
                  {formatCampaignEnum(issue.level)} · {issue.affectedContacts}
                </Badge>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {issue.message}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

const StartCampaignDialog = observer(function StartCampaignDialog({
  campaign,
  onOpenChange,
  open,
  organizationId,
  preparation,
}: {
  campaign: Campaign;
  onOpenChange: (open: boolean) => void;
  open: boolean;
  organizationId: string;
  preparation: CampaignPreparation | null;
}) {
  const { campaigns } = useRootStore();
  const blocked =
    preparation === null ||
    preparation.selectedContacts === 0 ||
    preparation.blockingFacts > 0;
  async function start(): Promise<void> {
    if (!blocked && (await campaigns.transition(organizationId, "start")))
      onOpenChange(false);
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!campaigns.isActing) onOpenChange(next);
      }}
    >
      <DialogContent className="max-h-[90svh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader className="pr-8">
          <DialogTitle>
            {campaign.status === "paused"
              ? "Resume campaign?"
              : "Start campaign?"}
          </DialogTitle>
          <DialogDescription>
            This activates exact campaign revision {campaign.publishedRevision}.
            Warnings do not remove recipients; blockers prevent new work.
          </DialogDescription>
        </DialogHeader>
        {campaigns.isPreparationLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }, (_, index) => (
              <Skeleton className="h-16 w-full" key={index} />
            ))}
          </div>
        ) : preparation === null ? (
          <ErrorBox>Preparation is unavailable.</ErrorBox>
        ) : (
          <PreparationSection preparation={preparation} />
        )}
        {preparation?.selectedContacts === 0 ? (
          <ErrorBox>Add at least one recipient before starting.</ErrorBox>
        ) : null}
        {campaigns.actionErrorMessage === null ? null : (
          <ErrorBox>{campaigns.actionErrorMessage}</ErrorBox>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            disabled={campaigns.isActing}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            disabled={blocked || campaigns.isActing}
            onClick={() => void start()}
          >
            {campaigns.isActing
              ? "Starting…"
              : campaign.status === "paused"
                ? "Resume campaign"
                : "Start campaign"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
});

function CampaignMoreMenu({
  campaign,
  onConfirm,
}: {
  campaign: Campaign;
  onConfirm: (confirmation: Exclude<Confirmation, null>) => void;
}) {
  const cancellable = ["draft", "scheduled", "running", "paused"].includes(
    campaign.status,
  );
  const deletable = ["draft", "canceled"].includes(campaign.status);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={<Button variant="outline" aria-label="More campaign actions" />}
      >
        <MoreHorizontal aria-hidden="true" />
        More
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {cancellable ? (
          <DropdownMenuItem onClick={() => onConfirm("cancel")}>
            <Ban aria-hidden="true" />
            Cancel campaign
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem onClick={() => onConfirm("revoke")}>
          <ShieldX aria-hidden="true" />
          Revoke revision
        </DropdownMenuItem>
        {deletable ? (
          <DropdownMenuItem
            variant="destructive"
            onClick={() => onConfirm("delete")}
          >
            <Trash2 aria-hidden="true" />
            Delete campaign
          </DropdownMenuItem>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ConfirmationDialog({
  confirmation,
  isActing,
  onConfirm,
  onOpenChange,
  onReasonChange,
  reason,
}: {
  confirmation: Confirmation;
  isActing: boolean;
  onConfirm: () => void;
  onOpenChange: (open: boolean) => void;
  onReasonChange: (value: string) => void;
  reason: string;
}) {
  const copy =
    confirmation === "pause"
      ? [
          "Pause campaign?",
          "Unstarted attempts return to pending. Active provider work is allowed to finish safely.",
        ]
      : confirmation === "cancel"
        ? [
            "Cancel campaign?",
            "New dispatch stops and unstarted recipients are marked cancelled. Existing calls, conversations, contacts, and evidence remain.",
          ]
        : confirmation === "delete"
          ? [
              "Delete campaign?",
              "Only draft or canceled campaigns can be deleted. Contacts and calls owned by other modules remain.",
            ]
          : [
              "Revoke this campaign revision?",
              "Emergency revocation cancels current authority and stops new dispatch for this exact revision.",
            ];
  return (
    <Dialog open={confirmation !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader className="pr-8">
          <DialogTitle>{copy[0]}</DialogTitle>
          <DialogDescription>{copy[1]}</DialogDescription>
        </DialogHeader>
        {confirmation === "revoke" ? (
          <div className="space-y-2">
            <Label htmlFor="campaign-revoke-reason">Reason</Label>
            <Textarea
              id="campaign-revoke-reason"
              className="min-h-24"
              maxLength={2000}
              value={reason}
              onChange={(event) => onReasonChange(event.target.value)}
            />
          </div>
        ) : null}
        <DialogFooter>
          <Button
            variant="outline"
            disabled={isActing}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            variant={confirmation === "pause" ? "default" : "destructive"}
            disabled={
              isActing || (confirmation === "revoke" && reason.trim() === "")
            }
            onClick={onConfirm}
          >
            {isActing
              ? "Working…"
              : confirmation === "pause"
                ? "Pause"
                : confirmation === "delete"
                  ? "Delete"
                  : confirmation === "revoke"
                    ? "Revoke revision"
                    : "Cancel campaign"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
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
      <dd className="min-w-0 break-words text-sm">{children}</dd>
    </div>
  );
}
function Metric({
  danger = false,
  label,
  value,
}: {
  danger?: boolean;
  label: string;
  value: number;
}) {
  return (
    <div className="bg-background p-4">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p
        className={
          danger
            ? "mt-2 text-2xl font-semibold text-destructive"
            : "mt-2 text-2xl font-semibold"
        }
      >
        {value.toLocaleString()}
      </p>
    </div>
  );
}
function ErrorBox({ children }: { children: ReactNode }) {
  return (
    <div
      className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
      role="alert"
    >
      {children}
    </div>
  );
}
function DetailsSkeleton() {
  return (
    <div className="space-y-5">
      {Array.from({ length: 9 }, (_, index) => (
        <Skeleton className="h-12 w-full" key={index} />
      ))}
    </div>
  );
}
function readString(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  return "";
}
function formatPercent(value: number): string {
  const percent = value <= 1 ? value * 100 : value;
  return `${Math.round(percent * 10) / 10}%`;
}

export { CampaignDetailsDrawer };
