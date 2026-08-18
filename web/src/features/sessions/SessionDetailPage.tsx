import { ArrowLeft, Check, Copy, RefreshCw } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button-variants";
import { Skeleton } from "@/components/ui/skeleton";
import { SessionDetails } from "@/features/sessions/SessionDetails";
import {
  formatSessionContact,
  formatSessionEnum,
} from "@/features/sessions/session-formatters";
import { SessionTimeline } from "@/features/sessions/SessionTimeline";
import {
  SESSION_TIMELINE_CATEGORIES,
  type SessionTimelineCategory,
  type SessionTimelineQuery,
} from "@/features/sessions/sessions.types";

type ShareState = "idle" | "copied" | "failed";

const SessionDetailPage = observer(function SessionDetailPage() {
  const { sessions } = useRootStore();
  const { organizationId, userSessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [shareState, setShareState] = useState<ShareState>("idle");
  const searchParamsKey = searchParams.toString();
  const timelineQuery = useMemo(
    () => parseTimelineQuery(new URLSearchParams(searchParamsKey)),
    [searchParamsKey],
  );

  useEffect(() => {
    if (organizationId !== undefined && userSessionId !== undefined) {
      void sessions.loadSelected(organizationId, userSessionId);
    }
    return sessions.clearSelected;
  }, [organizationId, sessions, userSessionId]);

  useEffect(() => {
    if (organizationId !== undefined && userSessionId !== undefined) {
      void sessions.loadTimeline(organizationId, userSessionId, timelineQuery);
    }
  }, [organizationId, sessions, timelineQuery, userSessionId]);

  if (organizationId === undefined || userSessionId === undefined) {
    return null;
  }
  const activeOrganizationId = organizationId;
  const activeUserSessionId = userSessionId;

  const selected = sessions.selectedSession;
  const collectionParams = new URLSearchParams(searchParams);
  collectionParams.delete("timeline_category");
  collectionParams.delete("technical");
  const collectionUrl = {
    pathname: `/org/${organizationId}/sessions`,
    search: collectionParams.toString(),
  };

  function setTimelineQuery(query: SessionTimelineQuery): void {
    const next = new URLSearchParams(searchParams);
    next.delete("timeline_category");
    for (const category of SESSION_TIMELINE_CATEGORIES) {
      if (category !== "technical" && query.categories.includes(category)) {
        next.append("timeline_category", category);
      }
    }
    if (query.includeTechnical) {
      next.set("technical", "1");
    } else {
      next.delete("technical");
    }
    setSearchParams(next, { replace: true });
  }

  async function copyShareLink(): Promise<void> {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setShareState("copied");
      window.setTimeout(() => setShareState("idle"), 2_000);
    } catch {
      setShareState("failed");
    }
  }

  function refresh(): void {
    void sessions.loadSelected(activeOrganizationId, activeUserSessionId);
    void sessions.loadTimeline(
      activeOrganizationId,
      activeUserSessionId,
      timelineQuery,
    );
  }

  return (
    <section
      className="min-w-0 space-y-6 p-4 sm:p-6"
      aria-labelledby="session-title"
    >
      <header className="min-w-0 space-y-4">
        <Link
          className={buttonVariants({ variant: "ghost", size: "sm" })}
          to={collectionUrl}
        >
          <ArrowLeft aria-hidden="true" />
          Back to sessions
        </Link>
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-2">
            <h1
              id="session-title"
              className="break-words text-2xl font-semibold tracking-tight"
            >
              {selected === null
                ? "Session timeline"
                : formatSessionContact(selected.contact)}
            </h1>
            {selected === null ? null : (
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant={
                    selected.state === "failed" ? "destructive" : "secondary"
                  }
                >
                  {formatSessionEnum(selected.state)}
                </Badge>
                <Badge variant="outline">
                  {formatSessionEnum(selected.entryChannel)}
                </Badge>
              </div>
            )}
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button
              variant="outline"
              disabled={
                sessions.isSelectedLoading || sessions.isTimelineLoading
              }
              onClick={refresh}
            >
              <RefreshCw aria-hidden="true" />
              Refresh
            </Button>
            <Button variant="outline" onClick={() => void copyShareLink()}>
              {shareState === "copied" ? (
                <Check aria-hidden="true" />
              ) : (
                <Copy aria-hidden="true" />
              )}
              {shareState === "copied" ? "Link copied" : "Share link"}
            </Button>
          </div>
        </div>
        {shareState === "failed" ? (
          <p className="text-sm text-destructive" role="alert">
            The link could not be copied. Copy it from the browser address bar.
          </p>
        ) : null}
      </header>

      {sessions.selectedErrorMessage !== null ? (
        <div className="border py-16 text-center" role="alert">
          <p className="text-sm font-medium">Session unavailable</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {sessions.selectedErrorMessage}
          </p>
          <Link
            className={buttonVariants({
              className: "mt-4",
              variant: "outline",
            })}
            to={collectionUrl}
          >
            Return to sessions
          </Link>
        </div>
      ) : selected === null ? (
        <SessionDetailSkeleton />
      ) : (
        <div className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <SessionTimeline
            organizationId={organizationId}
            query={timelineQuery}
            onChange={setTimelineQuery}
            onLoadMore={() =>
              void sessions.loadMoreTimeline(
                organizationId,
                userSessionId,
                timelineQuery,
              )
            }
          />
          <SessionDetails userSession={selected} />
        </div>
      )}
    </section>
  );
});

function parseTimelineQuery(
  searchParams: URLSearchParams,
): SessionTimelineQuery {
  const requested = searchParams.getAll("timeline_category");
  const categories = SESSION_TIMELINE_CATEGORIES.filter(
    (category): category is SessionTimelineCategory =>
      category !== "technical" && requested.includes(category),
  );
  return {
    categories,
    includeTechnical: searchParams.get("technical") === "1",
  };
}

function SessionDetailSkeleton() {
  return (
    <div className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
      <div className="space-y-5 border p-5">
        {Array.from({ length: 6 }, (_, index) => (
          <div className="space-y-3 border-b pb-5" key={index}>
            <Skeleton className="h-5 w-2/5" />
            <Skeleton className="h-12 w-full" />
          </div>
        ))}
      </div>
      <div className="space-y-4">
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    </div>
  );
}

export { SessionDetailPage };
