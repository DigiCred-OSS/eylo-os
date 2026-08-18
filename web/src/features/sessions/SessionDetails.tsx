import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import {
  formatSessionContact,
  formatSessionContactDetail,
  formatSessionDate,
  formatSessionDuration,
  formatSessionEnum,
} from "@/features/sessions/session-formatters";
import type { UserSession } from "@/features/sessions/sessions.types";

function SessionDetails({ userSession }: { userSession: UserSession }) {
  return (
    <aside className="min-w-0 space-y-4" aria-label="Session details">
      <DetailSection title="Contact">
        <p className="break-words font-medium">
          {formatSessionContact(userSession.contact)}
        </p>
        <p className="mt-1 break-words text-sm text-muted-foreground">
          {formatSessionContactDetail(userSession.contact)}
        </p>
        <DetailRow label="Contact ID" value={userSession.contact.id} mono />
      </DetailSection>

      <DetailSection title="Session">
        <div className="mb-4 flex flex-wrap gap-2">
          <Badge
            variant={
              userSession.state === "failed" ? "destructive" : "secondary"
            }
          >
            {formatSessionEnum(userSession.state)}
          </Badge>
          <Badge variant="outline">
            {formatSessionEnum(userSession.entryChannel)}
          </Badge>
        </div>
        <DetailRow label="Session ID" value={userSession.id} mono />
        <DetailRow
          label="Connections"
          value={String(userSession.connectionSequence)}
        />
        <DetailRow
          label="Duration"
          value={formatSessionDuration(userSession)}
        />
        <DetailDate label="Started" value={userSession.startedAt} />
        <DetailDate label="Last activity" value={userSession.lastActivityAt} />
        <DetailDate label="Disconnected" value={userSession.disconnectedAt} />
        <DetailDate label="Ended" value={userSession.endedAt} />
        <DetailRow
          label="End reason"
          value={
            userSession.endReason == null
              ? "Not recorded"
              : formatSessionEnum(userSession.endReason)
          }
        />
      </DetailSection>

      <DetailSection title="Activity">
        <CountGrid userSession={userSession} />
      </DetailSection>
    </aside>
  );
}

function DetailSection({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <section className="min-w-0 border p-4 sm:p-5">
      <h2 className="mb-4 font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function DetailRow({
  label,
  mono = false,
  value,
}: {
  label: string;
  mono?: boolean;
  value: ReactNode;
}) {
  return (
    <div className="grid min-w-0 gap-1 border-t py-3 first:border-t-0 first:pt-0 sm:grid-cols-[8rem_minmax(0,1fr)]">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className={`min-w-0 break-all text-sm ${mono ? "font-mono" : ""}`}>
        {value}
      </p>
    </div>
  );
}

function DetailDate({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  const date = formatSessionDate(value);
  return (
    <DetailRow
      label={label}
      value={
        value == null ? (
          date.label
        ) : (
          <time dateTime={value} title={date.title}>
            {date.label}
          </time>
        )
      }
    />
  );
}

function CountGrid({ userSession }: { userSession: UserSession }) {
  const counts = [
    ["Conversations", userSession.counts.conversations],
    ["Messages", userSession.counts.messages],
    ["Agent runs", userSession.counts.agentRuns],
    ["Voice sessions", userSession.counts.voiceSessions],
    ["Calls", userSession.counts.telephonyCalls],
    ["Timeline events", userSession.counts.timelineEvents],
  ] as const;
  return (
    <dl className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3 xl:grid-cols-2">
      {counts.map(([label, value]) => (
        <div className="min-w-0 bg-background p-3" key={label}>
          <dt className="break-words text-xs text-muted-foreground">{label}</dt>
          <dd className="mt-1 text-lg font-semibold tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export { SessionDetails };
