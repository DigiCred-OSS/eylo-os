import { ExternalLink, Trash2, X } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  formatCallDuration,
  formatTelephonyDate,
  formatTelephonyEnum,
} from "@/features/telephony/telephony-formatters";
import type { TelephonyCall } from "@/features/telephony/telephony.types";

interface CallDetailsDrawerProps {
  callId: string | undefined;
  onClose: () => void;
  organizationId: string;
}

const CallDetailsDrawer = observer(function CallDetailsDrawer({
  callId,
  onClose,
  organizationId,
}: CallDetailsDrawerProps) {
  const { telephony } = useRootStore();
  const store = telephony.calls;
  const call = store.selectedCall;
  const [deleteOpen, setDeleteOpen] = useState(false);

  async function requestDeletion(): Promise<void> {
    if (call === null) return;
    if (await store.requestDeletion(call.id)) setDeleteOpen(false);
  }

  return (
    <>
      <Drawer
        open={callId !== undefined}
        onOpenChange={(open) => {
          if (!open) onClose();
        }}
        swipeDirection="right"
      >
        <DrawerContent className="[--drawer-content-width:min(100%,52rem)]">
          <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
            <DrawerTitle>
              {call === null
                ? "Telephony call"
                : `${call.fromNumber ?? "Unknown"} → ${call.toNumber ?? "Unknown"}`}
            </DrawerTitle>
            <DrawerDescription>
              Canonical call state, exact provider and Agent revision, linked
              conversation, timing, and transfer outcome.
            </DrawerDescription>
          </DrawerHeader>
          <Button
            className="absolute top-4 right-4 z-20"
            variant="ghost"
            size="icon"
            aria-label="Close call"
            onClick={onClose}
          >
            <X aria-hidden="true" />
          </Button>
          <div className="min-h-0 flex-1 overflow-y-auto p-5">
            {store.isSelectedLoading && call === null ? (
              <DetailsSkeleton />
            ) : store.selectedErrorMessage !== null ? (
              <ErrorBox>{store.selectedErrorMessage}</ErrorBox>
            ) : call === null ? null : (
              <CallDetails
                call={call}
                organizationId={organizationId}
                agentName={telephony.agentName(call.agentId)}
                configName={telephony.configName(call.providerConfigId)}
              />
            )}
            {store.deletionJob === null ? null : (
              <div className="mt-5 border p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">Deletion requested</p>
                  <Badge
                    variant={
                      store.deletionJob.status === "failed"
                        ? "destructive"
                        : "outline"
                    }
                  >
                    {formatTelephonyEnum(store.deletionJob.status)}
                  </Badge>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Job …{store.deletionJob.id.slice(-12)} removes Eylo-owned call
                  data asynchronously. It makes no provider-side deletion claim.
                </p>
              </div>
            )}
            {store.actionErrorMessage === null ? null : (
              <div className="mt-4">
                <ErrorBox>{store.actionErrorMessage}</ErrorBox>
              </div>
            )}
          </div>
          {call === null || store.deletionJob !== null ? null : (
            <DrawerFooter className="flex-row border-t p-4">
              <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
                <Trash2 aria-hidden="true" />
                Delete call data
              </Button>
            </DrawerFooter>
          )}
        </DrawerContent>
      </Drawer>
      <Dialog
        open={deleteOpen}
        onOpenChange={(open) => {
          if (!store.isActing) setDeleteOpen(open);
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader className="pr-8">
            <DialogTitle>Delete this call from Eylo?</DialogTitle>
            <DialogDescription>
              An asynchronous job removes the owned call record and its
              Eylo-owned dependents. Campaigns and contacts remain.
              Provider-held data is outside this request.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              disabled={store.isActing}
              onClick={() => setDeleteOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={store.isActing}
              onClick={() => void requestDeletion()}
            >
              {store.isActing ? "Requesting…" : "Request deletion"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
});

function CallDetails({
  agentName,
  call,
  configName,
  organizationId,
}: {
  agentName: string;
  call: TelephonyCall;
  configName: string;
  organizationId: string;
}) {
  const created = formatTelephonyDate(call.createdAt);
  const updated = formatTelephonyDate(call.updatedAt);
  const started = formatTelephonyDate(call.startedAt);
  const connected = formatTelephonyDate(call.connectedAt);
  const ended = formatTelephonyDate(call.endedAt);
  const opener = formatTelephonyDate(call.openerDeliveredAt);
  const transferred = formatTelephonyDate(call.transferredAt);
  return (
    <div className="space-y-8">
      <DetailsSection title="Overview">
        <DetailRow label="Status">
          <Badge variant={call.status === "failed" ? "destructive" : "outline"}>
            {formatTelephonyEnum(call.status)}
          </Badge>
        </DetailRow>
        <DetailRow label="Direction">
          <Badge variant="outline">{formatTelephonyEnum(call.direction)}</Badge>
        </DetailRow>
        <DetailRow label="From">{call.fromNumber ?? "Not recorded"}</DetailRow>
        <DetailRow label="To">{call.toNumber ?? "Not recorded"}</DetailRow>
        <DetailRow label="End reason">
          {call.endedReason ?? "Not recorded"}
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Authority">
        <DetailRow label="Provider">
          <Badge variant="outline">{formatTelephonyEnum(call.provider)}</Badge>
        </DetailRow>
        <DetailRow label="Configuration">
          <Link
            className="inline-flex items-center gap-1 underline underline-offset-4"
            to={`/org/${organizationId}/providers/telephony/${call.providerConfigId}`}
          >
            {configName} · revision {call.providerConfigRevision}
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </Link>
        </DetailRow>
        <DetailRow label="Agent">
          {call.agentId === null || call.agentId === undefined ? (
            "Not recorded"
          ) : (
            <Link
              className="underline underline-offset-4"
              to={`/org/${organizationId}/agents/${call.agentId}`}
            >
              {agentName} · revision {call.agentRevision}
            </Link>
          )}
        </DetailRow>
        <DetailRow label="Provider call ID">
          <code className="break-all text-xs">
            {call.callSid ?? "Not recorded"}
          </code>
        </DetailRow>
        <DetailRow label="Provider status">
          {call.providerStatus ?? "Not recorded"}
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Timing">
        <DetailRow label="Started">
          {call.startedAt === null || call.startedAt === undefined ? (
            started.label
          ) : (
            <time dateTime={call.startedAt} title={started.title}>
              {started.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="Connected">
          {call.connectedAt === null || call.connectedAt === undefined ? (
            connected.label
          ) : (
            <time dateTime={call.connectedAt} title={connected.title}>
              {connected.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="Ended">
          {call.endedAt === null || call.endedAt === undefined ? (
            ended.label
          ) : (
            <time dateTime={call.endedAt} title={ended.title}>
              {ended.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="Duration">
          {formatCallDuration(call.durationSeconds)}
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Conversation and product">
        <DetailRow label="Conversation">
          {call.conversationId === null || call.conversationId === undefined ? (
            "Not linked"
          ) : (
            <Link
              className="underline underline-offset-4"
              to={`/org/${organizationId}/conversations/${call.conversationId}`}
            >
              Open conversation
            </Link>
          )}
        </DetailRow>
        <DetailRow label="Voice session">
          {call.voiceSessionId === null || call.voiceSessionId === undefined ? (
            "Not linked"
          ) : (
            <Link
              className="underline underline-offset-4"
              to={`/org/${organizationId}/voice-sessions/${call.voiceSessionId}`}
            >
              Open voice session
            </Link>
          )}
        </DetailRow>
        <DetailRow label="Campaign">
          {call.campaignId === null || call.campaignId === undefined ? (
            "Not linked"
          ) : (
            <Link
              className="underline underline-offset-4"
              to={`/org/${organizationId}/outbound/campaigns/${call.campaignId}`}
            >
              Open campaign
            </Link>
          )}
        </DetailRow>
        <DetailRow label="Phone number">
          {call.phoneNumberId === null || call.phoneNumberId === undefined ? (
            "Not linked"
          ) : (
            <Link
              className="underline underline-offset-4"
              to={`/org/${organizationId}/telephony/numbers/${call.phoneNumberId}`}
            >
              Open phone number
            </Link>
          )}
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Opener and transfer">
        <DetailRow label="Opener">
          <Badge variant="outline">
            {formatTelephonyEnum(call.openerDeliveryStatus)}
          </Badge>
        </DetailRow>
        <DetailRow label="Opener delivered">
          {call.openerDeliveredAt === null ||
          call.openerDeliveredAt === undefined ? (
            opener.label
          ) : (
            <time dateTime={call.openerDeliveredAt} title={opener.title}>
              {opener.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="Transfer">
          <Badge variant="outline">
            {formatTelephonyEnum(call.transferStatus)}
          </Badge>
        </DetailRow>
        <DetailRow label="Transfer to">
          {call.transferTo ?? "Not recorded"}
        </DetailRow>
        <DetailRow label="Transfer reason">
          {call.transferReason ?? "Not recorded"}
        </DetailRow>
        <DetailRow label="Transferred">
          {call.transferredAt === null || call.transferredAt === undefined ? (
            transferred.label
          ) : (
            <time dateTime={call.transferredAt} title={transferred.title}>
              {transferred.label}
            </time>
          )}
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Record">
        <DetailRow label="Created">
          <time dateTime={call.createdAt} title={created.title}>
            {created.label}
          </time>
        </DetailRow>
        <DetailRow label="Updated">
          <time dateTime={call.updatedAt} title={updated.title}>
            {updated.label}
          </time>
        </DetailRow>
        <DetailRow label="ID">
          <code className="break-all text-xs">{call.id}</code>
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
      <dd className="min-w-0 break-words text-sm">{children}</dd>
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
        <Skeleton className="h-10 w-full" key={index} />
      ))}
    </div>
  );
}

export { CallDetailsDrawer };
