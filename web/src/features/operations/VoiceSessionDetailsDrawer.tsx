import { ExternalLink, X } from "lucide-react";
import { observer } from "mobx-react-lite";
import type { ReactNode } from "react";
import { Link } from "react-router";

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
  formatDuration,
  formatOperationDate,
  formatOperationEnum,
} from "@/features/operations/operation-formatters";
import type { VoiceSessionDetail } from "@/features/operations/operations.types";

interface VoiceSessionDetailsDrawerProps {
  onClose: () => void;
  organizationId: string;
  voiceSessionId: string | undefined;
}

const VoiceSessionDetailsDrawer = observer(function VoiceSessionDetailsDrawer({
  onClose,
  organizationId,
  voiceSessionId,
}: VoiceSessionDetailsDrawerProps) {
  const { operations } = useRootStore();
  const store = operations.voiceSessions;
  const session = store.selectedSession;
  return (
    <Drawer
      open={voiceSessionId !== undefined}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      swipeDirection="right"
    >
      <DrawerContent className="[--drawer-content-width:min(100%,52rem)]">
        <DrawerHeader className="border-b p-5 pr-14 pb-5 text-left">
          <DrawerTitle>
            {session === null
              ? "Voice session"
              : `Session …${session.id.slice(-12)}`}
          </DrawerTitle>
          <DrawerDescription>
            Canonical transcript, provider stack, call timing, and
            conversation-owned recording access.
          </DrawerDescription>
        </DrawerHeader>
        <Button
          className="absolute top-4 right-4 z-20"
          variant="ghost"
          size="icon"
          aria-label="Close voice session"
          title="Close"
          onClick={onClose}
        >
          <X aria-hidden="true" />
        </Button>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {store.isSelectedLoading && session === null ? (
            <DetailsSkeleton />
          ) : store.selectedErrorMessage !== null ? (
            <div
              className="border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
              role="alert"
            >
              {store.selectedErrorMessage}
            </div>
          ) : session !== null ? (
            <SessionDetails
              session={session}
              organizationId={organizationId}
              agentName={operations.agentName(session.agentId)}
            />
          ) : null}
        </div>
      </DrawerContent>
    </Drawer>
  );
});

function SessionDetails({
  agentName,
  organizationId,
  session,
}: {
  agentName: string;
  organizationId: string;
  session: VoiceSessionDetail;
}) {
  const started = formatOperationDate(session.startedAt);
  const ended = formatOperationDate(session.endedAt ?? null);
  const provider =
    session.realtimeVendor !== null && session.realtimeVendor !== undefined
      ? [session.realtimeVendor, session.realtimeModel]
          .filter(Boolean)
          .join(" · ")
      : `STT ${[session.sttVendor, session.sttModel].filter(Boolean).join(" · ") || "not recorded"} / TTS ${[session.ttsVendor, session.ttsModel, session.ttsVoice].filter(Boolean).join(" · ") || "not recorded"}`;
  return (
    <div className="space-y-8">
      <DetailsSection title="Overview">
        <DetailRow label="Status">
          <Badge variant="outline">{formatOperationEnum(session.status)}</Badge>
        </DetailRow>
        <DetailRow label="Runtime">
          <Badge variant="outline">
            {formatOperationEnum(session.runtimeMode)}
          </Badge>
        </DetailRow>
        <DetailRow label="Transport">
          {formatOperationEnum(session.transport)}
        </DetailRow>
        <DetailRow label="Agent">
          {session.agentId === null || session.agentId === undefined ? (
            agentName
          ) : (
            <Link
              className="underline underline-offset-4"
              to={`/org/${organizationId}/agents/${session.agentId}`}
            >
              {agentName} · revision {session.agentRevision}
            </Link>
          )}
        </DetailRow>
        <DetailRow label="Conversation">
          <Link
            className="inline-flex items-center gap-1 underline underline-offset-4"
            to={`/org/${organizationId}/conversations/${session.conversationId}`}
          >
            Open conversation{" "}
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </Link>
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Timing">
        <DetailRow label="Started">
          <time dateTime={session.startedAt} title={started.title}>
            {started.label}
          </time>
        </DetailRow>
        <DetailRow label="Ended">
          {session.endedAt === null || session.endedAt === undefined ? (
            ended.label
          ) : (
            <time dateTime={session.endedAt} title={ended.title}>
              {ended.label}
            </time>
          )}
        </DetailRow>
        <DetailRow label="Duration">
          {formatDuration(session.durationMs)}
        </DetailRow>
        <DetailRow label="End reason">
          {session.endedReason ?? "Not recorded"}
        </DetailRow>
        <DetailRow label="User talk time">
          {formatDuration(session.userTalkTimeMs)}
        </DetailRow>
        <DetailRow label="Assistant talk time">
          {formatDuration(session.assistantTalkTimeMs)}
        </DetailRow>
      </DetailsSection>
      <DetailsSection title="Provider path">
        <DetailRow label="Providers">
          <span className="break-words">{provider || "Not recorded"}</span>
        </DetailRow>
        {session.telephonyProvider === null ||
        session.telephonyProvider === undefined ? null : (
          <>
            <DetailRow label="Telephony">{session.telephonyProvider}</DetailRow>
            <DetailRow label="From">
              {session.fromNumber ?? "Not recorded"}
            </DetailRow>
            <DetailRow label="To">
              {session.toNumber ?? "Not recorded"}
            </DetailRow>
          </>
        )}
      </DetailsSection>
      <DetailsSection title="Canonical transcript">
        <DetailRow label="State">
          <Badge variant="outline">
            {formatOperationEnum(session.canonicalState)}
          </Badge>
        </DetailRow>
        <DetailRow label="Messages">{session.canonicalMessageCount}</DetailRow>
        <DetailRow label="Source complete">
          {session.canonicalSourceComplete === null ||
          session.canonicalSourceComplete === undefined
            ? "Unknown"
            : session.canonicalSourceComplete
              ? "Yes"
              : "No"}
        </DetailRow>
        <DetailRow label="Failure code">
          {session.canonicalFailureCode ?? "None"}
        </DetailRow>
      </DetailsSection>
      <section className="space-y-3">
        <div>
          <h2 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            Transcript segments
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Ordered speech, tools, events, and interruption outcomes. Partial
            vendor text is not treated as canonical.
          </p>
        </div>
        {(session.segments ?? []).length === 0 ? (
          <div className="border py-8 text-center text-sm text-muted-foreground">
            No transcript segments
          </div>
        ) : (
          <div className="divide-y border">
            {session.segments?.map((segment) => (
              <article className="space-y-2 p-3" key={segment.id}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline">
                      {formatOperationEnum(segment.role)}
                    </Badge>
                    <Badge variant="outline">
                      {formatOperationEnum(segment.segmentType)}
                    </Badge>
                    {segment.speechOutcome === null ||
                    segment.speechOutcome === undefined ? null : (
                      <Badge variant="outline">
                        {formatOperationEnum(segment.speechOutcome)}
                      </Badge>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    #{segment.sequence}
                  </span>
                </div>
                {segment.text === null || segment.text === undefined ? null : (
                  <p className="whitespace-pre-wrap break-words text-sm leading-6">
                    {segment.text}
                  </p>
                )}
                {segment.toolName === null ||
                segment.toolName === undefined ? null : (
                  <p className="text-xs text-muted-foreground">
                    Tool: {segment.toolName}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
        {session.segmentsHasMore ? (
          <p className="text-sm text-muted-foreground">
            Showing the first {session.segmentLimit} of {session.segmentTotal}{" "}
            segments.
          </p>
        ) : null}
      </section>
      <section className="space-y-2 border-t pt-5">
        <h2 className="font-medium">Recordings</h2>
        <p className="text-sm leading-6 text-muted-foreground">
          Recording tracks are conversation-owned and require
          bearer-authenticated loading. Open the conversation to play or
          download them safely.
        </p>
        <Button
          nativeButton={false}
          render={
            <Link
              to={`/org/${organizationId}/conversations/${session.conversationId}`}
            />
          }
          variant="outline"
        >
          <ExternalLink aria-hidden="true" />
          Open conversation recordings
        </Button>
      </section>
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
      <dd className="min-w-0 break-words text-sm">{children}</dd>
    </div>
  );
}
function DetailsSkeleton() {
  return (
    <div className="space-y-5">
      {Array.from({ length: 8 }, (_, index) => (
        <Skeleton key={index} className="h-10 w-full" />
      ))}
    </div>
  );
}

export { VoiceSessionDetailsDrawer };
