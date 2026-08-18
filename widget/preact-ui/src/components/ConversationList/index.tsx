// components/ConversationList/index.tsx
import type { FC } from "preact/compat";
import type { Conversation } from "@eylo/modules/conversation";
import { FaExclamationTriangle, FaRegComments } from "react-icons/fa";

import { PATHS } from "../../app";
import PlusIcon from "../../assets/icons/PlusIcon";
import {
  useConversations,
  useLastMessage,
  useMessageContentPlainText,
} from "../../hooks/useEyloStore";
import { useIsAgentWorking } from "../../hooks/useIsAgentWorking";
import { useNavigate } from "../../library/MemoryRouter";
import ChatWidgetContainer from "../ChatWidgetContainer";
import { Card, CardHeader, CardTitle, CardDescription } from "../../design-system/components/Card";
import { Empty } from "../../design-system/components/Empty";
import { Skeleton } from "../../design-system/components/Skeleton";
import { Button } from "../../design-system/components/Button";
import { Stack } from "../../design-system/components/Stack";
import { Box } from "../../design-system/components/Box";
import { Badge } from "../../design-system/components/Badge";
import { Flex } from "../../design-system/components/Flex";
import { formatTimestamp } from "../../utils";
import styles from "./ConversationList.module.css";

// Subcomponent to handle individual conversation item
const ConversationItem: FC<{ conversation: Conversation; onClick: (id: string) => void }> = ({
  conversation,
  onClick,
}) => {
  const lastMessage = useLastMessage(conversation.id);
  const messageText = useMessageContentPlainText(lastMessage);
  const isAgentWorking = useIsAgentWorking(conversation.id);

  const senderName =
    lastMessage?.contact?.name || lastMessage?.senderParticipant?.entityKind || "Unknown";

  const messagePreview =
    lastMessage && messageText ? `${senderName}: ${messageText}` : "No messages yet";
  const conversationTitle = conversation.title || "New conversation";

  const openConversation = () => onClick(conversation.id);

  return (
    <Card
      className={styles.conversationItem}
      shadow="none"
      borderRadius="none"
      interactive
      key={conversation.id}
      role="button"
      tabIndex={0}
      aria-label={`Open ${conversationTitle}`}
      onClick={openConversation}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openConversation();
        }
      }}
    >
      <CardHeader className={styles.conversationHeader}>
        <Flex align="start" justify="between" gap="xs" className={styles.conversationTopLine}>
          <CardTitle className={styles.conversationTitle}>{conversationTitle}</CardTitle>
          <Flex align="center" gap="xs">
            {conversation.unreadCount > 0 && (
              <Badge variant="default" aria-label={`${conversation.unreadCount} unread messages`}>
                {conversation.unreadCount}
              </Badge>
            )}
            {isAgentWorking && <Badge variant="secondary">🤖 Agent busy</Badge>}
          </Flex>
        </Flex>
        <CardDescription className={styles.messagePreview} title={messagePreview}>
          {messagePreview && messagePreview.length > 50
            ? `${messagePreview.substring(0, 50)}...`
            : messagePreview}
        </CardDescription>
        <CardDescription className={styles.timestamp}>
          {formatTimestamp(conversation.updatedAt)}
        </CardDescription>
      </CardHeader>
    </Card>
  );
};

const ConversationList: FC = () => {
  const navigate = useNavigate();

  // Use our new reactive hook that handles fetching, loading, and errors.
  const {
    activeConversations: conversations,
    loading,
    loadingMore,
    hasMore,
    loadMore,
    error,
  } = useConversations();

  const handleConversationClick = (conversationId: string) => {
    navigate(PATHS.CONVERSATION_DETAILS, { id: conversationId });
  };

  return (
    <>
      <ChatWidgetContainer.ChatHeader title="Conversations" />
      <ChatWidgetContainer.ChatContent>
        <Box>
          <Stack>
            {/* Active Conversations */}
            {loading && (
              <Stack spacing="2xs">
                <Skeleton height="4xl" width="full" />
                <Skeleton height="4xl" width="full" />
                <Skeleton height="4xl" width="full" />
              </Stack>
            )}

            {error && (
              <Empty
                icon={<FaExclamationTriangle aria-hidden="true" />}
                title="Error loading conversations"
                description={error.message}
              />
            )}

            {!loading && !error && conversations.length === 0 ? (
              <Empty
                icon={<FaRegComments aria-hidden="true" />}
                title="No active conversations"
                description="Start a new conversation to get started"
              />
            ) : (
              !loading &&
              !error && (
                <Stack>
                  {conversations.map((conversation) => (
                    <ConversationItem
                      key={conversation.id}
                      conversation={conversation}
                      onClick={handleConversationClick}
                    />
                  ))}
                  {hasMore && (
                    <Button
                      variant="secondary"
                      size="sm"
                      width="full"
                      disabled={loadingMore}
                      onClick={() => void loadMore()}
                    >
                      {loadingMore ? "Loading..." : "Load older conversations"}
                    </Button>
                  )}
                </Stack>
              )
            )}
          </Stack>
        </Box>
      </ChatWidgetContainer.ChatContent>
      <ChatWidgetContainer.ChatFooter>
        <Button variant="default" size="md" width="full" onClick={() => navigate(PATHS.AGENT_LIST)}>
          <PlusIcon />
          Start a new conversation
        </Button>
      </ChatWidgetContainer.ChatFooter>
    </>
  );
};

export default ConversationList;
