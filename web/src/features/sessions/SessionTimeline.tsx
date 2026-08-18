import {
  Activity,
  AudioLines,
  Bot,
  Cable,
  ChevronDown,
  FileText,
  MessageSquareText,
  MessagesSquare,
  Phone,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { observer } from "mobx-react-lite";
import { Link } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  formatSessionDate,
  formatSessionEnum,
} from "@/features/sessions/session-formatters";
import {
  SESSION_TIMELINE_CATEGORIES,
  type SessionTimelineCategory,
  type SessionTimelineEvent,
  type SessionTimelineQuery,
} from "@/features/sessions/sessions.types";

interface SessionTimelineProps {
  onChange: (query: SessionTimelineQuery) => void;
  onLoadMore: () => void;
  organizationId: string;
  query: SessionTimelineQuery;
}

const visibleCategoryOptions = SESSION_TIMELINE_CATEGORIES.filter(
  (category) => category !== "technical",
);

const categoryIcons: Record<SessionTimelineCategory, LucideIcon> = {
  session: Activity,
  conversation: MessagesSquare,
  message: MessageSquareText,
  agent: Bot,
  tool: Wrench,
  file: FileText,
  voice: AudioLines,
  telephony: Phone,
  technical: Cable,
};

const SessionTimeline = observer(function SessionTimeline({
  onChange,
  onLoadMore,
  organizationId,
  query,
}: SessionTimelineProps) {
  const { sessions } = useRootStore();

  function toggleCategory(category: SessionTimelineCategory): void {
    const selected = query.categories.includes(category);
    onChange({
      ...query,
      categories: selected
        ? query.categories.filter((value) => value !== category)
        : [...query.categories, category],
    });
  }

  return (
    <section
      className="min-w-0 border"
      aria-labelledby="session-timeline-title"
    >
      <header className="space-y-4 border-b p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 id="session-timeline-title" className="font-semibold">
              Interaction timeline
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Stable display order uses event time, then event ID. It does not
              imply cross-system execution order.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Switch
              checked={query.includeTechnical}
              aria-label="Show technical events"
              onCheckedChange={(includeTechnical) =>
                onChange({ ...query, includeTechnical })
              }
            />
            Show technical events
          </label>
        </div>

        <div
          className="flex flex-wrap gap-2"
          aria-label="Timeline categories"
          role="group"
        >
          <Button
            size="sm"
            variant={query.categories.length === 0 ? "secondary" : "outline"}
            aria-pressed={query.categories.length === 0}
            onClick={() => onChange({ ...query, categories: [] })}
          >
            All events
          </Button>
          {visibleCategoryOptions.map((category) => {
            const selected = query.categories.includes(category);
            return (
              <Button
                key={category}
                size="sm"
                variant={selected ? "secondary" : "outline"}
                aria-pressed={selected}
                onClick={() => toggleCategory(category)}
              >
                <TimelineCategoryIcon category={category} />
                {formatSessionEnum(category)}
              </Button>
            );
          })}
        </div>
      </header>

      {sessions.timelineErrorMessage !== null ? (
        <div className="p-8 text-center" role="alert">
          <p className="text-sm font-medium">Timeline unavailable</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {sessions.timelineErrorMessage}
          </p>
        </div>
      ) : sessions.isTimelineLoading ? (
        <TimelineSkeleton />
      ) : sessions.timeline.length === 0 ? (
        <div className="p-10 text-center">
          <p className="text-sm font-medium">No matching events</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Change the category selection or include technical events.
          </p>
        </div>
      ) : (
        <ol className="divide-y" aria-label="Session events">
          {sessions.timeline.map((event) => (
            <TimelineEventItem
              event={event}
              key={event.id}
              organizationId={organizationId}
            />
          ))}
        </ol>
      )}

      {sessions.timelineHasMore ? (
        <div className="border-t p-3 text-center">
          <Button
            variant="outline"
            disabled={sessions.isLoadingMoreTimeline}
            onClick={onLoadMore}
          >
            <ChevronDown aria-hidden="true" />
            {sessions.isLoadingMoreTimeline ? "Loading…" : "Load more events"}
          </Button>
        </div>
      ) : sessions.timeline.length > 0 ? (
        <p className="border-t p-3 text-center text-xs text-muted-foreground">
          Showing all {sessions.timelineTotal} matching events
        </p>
      ) : null}
    </section>
  );
});

function TimelineEventItem({
  event,
  organizationId,
}: {
  event: SessionTimelineEvent;
  organizationId: string;
}) {
  const occurred = formatSessionDate(event.occurredAt);
  const details = Object.entries(event.details ?? {});
  return (
    <li className="relative min-w-0 p-4 pl-10 sm:p-5 sm:pl-12">
      <span
        className="absolute top-6 left-4 size-2 rounded-full bg-foreground sm:left-5"
        aria-hidden="true"
      />
      <div className="min-w-0 space-y-3">
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="break-words font-medium">{event.label}</p>
              <Badge
                variant={
                  event.severity === "danger" ? "destructive" : "secondary"
                }
              >
                <TimelineCategoryIcon category={event.category} />
                {formatSessionEnum(event.category)}
              </Badge>
            </div>
            <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
              {event.eventType}
            </p>
          </div>
          <time
            className="shrink-0 text-xs text-muted-foreground"
            dateTime={event.occurredAt}
            title={occurred.title}
          >
            {occurred.label}
          </time>
        </div>

        {details.length > 0 ? (
          <dl className="grid min-w-0 gap-x-4 gap-y-2 text-sm sm:grid-cols-[max-content_minmax(0,1fr)]">
            {details.map(([key, value]) => (
              <TimelineDetail
                detailKey={key}
                key={key}
                organizationId={organizationId}
                value={value}
              />
            ))}
          </dl>
        ) : null}

        <p className="break-all text-xs text-muted-foreground">
          Subject: {formatSessionEnum(event.subjectType)} · {event.subjectId}
        </p>
      </div>
    </li>
  );
}

function TimelineCategoryIcon({
  category,
}: {
  category: SessionTimelineCategory;
}) {
  const Icon = categoryIcons[category];
  return <Icon aria-hidden="true" data-icon="inline-start" />;
}

function TimelineDetail({
  detailKey,
  organizationId,
  value,
}: {
  detailKey: string;
  organizationId: string;
  value: unknown;
}) {
  const label = formatSessionEnum(detailKey);
  const rendered = formatTimelineValue(value);
  return (
    <>
      <dt className="font-medium text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-all">
        {detailKey === "conversation_id" && typeof value === "string" ? (
          <Link
            className="underline underline-offset-4"
            to={`/org/${organizationId}/conversations/${value}`}
          >
            {rendered}
          </Link>
        ) : (
          rendered
        )}
      </dd>
    </>
  );
}

function formatTimelineValue(value: unknown): string {
  if (value == null) {
    return "Not recorded";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return String(value);
}

function TimelineSkeleton() {
  return (
    <div className="divide-y">
      {Array.from({ length: 6 }, (_, index) => (
        <div className="space-y-3 p-5" key={index}>
          <div className="flex justify-between gap-4">
            <Skeleton className="h-5 w-2/5" />
            <Skeleton className="h-4 w-36" />
          </div>
          <Skeleton className="h-4 w-3/4" />
        </div>
      ))}
    </div>
  );
}

export { SessionTimeline };
