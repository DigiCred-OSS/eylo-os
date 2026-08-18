import { ArrowLeft, Check, Copy, RefreshCw } from "lucide-react";
import { observer } from "mobx-react-lite";
import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router";

import { useRootStore } from "@/app/use-root-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ConversationDetails } from "@/features/conversations/ConversationDetails";
import { ConversationTranscript } from "@/features/conversations/ConversationTranscript";
import { formatConversationEnum } from "@/features/conversations/conversation-formatters";

type ShareState = "idle" | "copied" | "failed";

const ConversationDetailPage = observer(function ConversationDetailPage() {
  const { conversations } = useRootStore();
  const { conversationId, organizationId } = useParams();
  const location = useLocation();
  const [shareState, setShareState] = useState<ShareState>("idle");

  useEffect(() => {
    if (organizationId !== undefined && conversationId !== undefined) {
      void conversations.loadSelected(organizationId, conversationId);
    }
    return conversations.clearSelected;
  }, [conversationId, conversations, organizationId]);

  if (organizationId === undefined || conversationId === undefined) {
    return null;
  }

  const selected = conversations.selectedConversation;
  const collectionUrl = {
    pathname: `/org/${organizationId}/conversations`,
    search: location.search,
  };

  async function copyShareLink(): Promise<void> {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setShareState("copied");
      window.setTimeout(() => setShareState("idle"), 2_000);
    } catch {
      setShareState("failed");
    }
  }

  return (
    <section
      className="min-w-0 space-y-6 p-4 sm:p-6"
      aria-labelledby="conversation-title"
    >
      <header className="min-w-0 space-y-4">
        <Button
          nativeButton={false}
          variant="ghost"
          size="sm"
          render={<Link to={collectionUrl} />}
        >
          <ArrowLeft aria-hidden="true" />
          Back to conversations
        </Button>
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-2">
            <h1
              id="conversation-title"
              className="break-words text-2xl font-semibold tracking-tight"
            >
              {selected?.title?.trim() || "Conversation details"}
            </h1>
            {selected === null ? null : (
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  variant={selected.status === "ACTIVE" ? "default" : "outline"}
                >
                  {formatConversationEnum(selected.status)}
                </Badge>
                <Badge variant="secondary">
                  {formatConversationEnum(selected.channel)}
                </Badge>
              </div>
            )}
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button
              variant="outline"
              disabled={conversations.isSelectedLoading}
              onClick={() =>
                void conversations.loadSelected(organizationId, conversationId)
              }
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

      {conversations.selectedErrorMessage !== null ? (
        <div className="border py-16 text-center" role="alert">
          <p className="text-sm font-medium">Conversation unavailable</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {conversations.selectedErrorMessage}
          </p>
          <Button
            className="mt-4"
            nativeButton={false}
            variant="outline"
            render={<Link to={collectionUrl} />}
          >
            Return to conversations
          </Button>
        </div>
      ) : selected === null ? (
        <ConversationDetailSkeleton />
      ) : (
        <div className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
          <ConversationTranscript
            conversation={selected}
            onLoadMore={() =>
              void conversations.loadMoreMessages(
                organizationId,
                conversationId,
              )
            }
          />
          <ConversationDetails
            conversation={selected}
            organizationId={organizationId}
          />
        </div>
      )}
    </section>
  );
});

function ConversationDetailSkeleton() {
  return (
    <div className="grid min-w-0 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
      <div className="space-y-5 border p-5">
        {Array.from({ length: 5 }, (_, index) => (
          <div className="space-y-3 border-b pb-5" key={index}>
            <Skeleton className="h-5 w-2/5" />
            <Skeleton className="h-20 w-full" />
          </div>
        ))}
      </div>
      <div className="space-y-4">
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    </div>
  );
}

export { ConversationDetailPage };
