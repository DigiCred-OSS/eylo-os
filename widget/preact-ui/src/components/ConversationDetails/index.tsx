import { memo, useEffect, useMemo, useRef, useState, type FC } from "preact/compat";
import {
  FaRegComments,
  FaRegThumbsDown,
  FaRegThumbsUp,
  FaSearch,
  FaStop,
  FaThumbsDown,
  FaThumbsUp,
} from "react-icons/fa";
import { PATHS } from "../../app";

import { RiRefreshLine } from "react-icons/ri";
import {
  useConnectionStatus,
  useConversation,
  useConversationMessages,
  useMessageContent,
  useWidgetMessagePayload,
  useWidgetResponseData,
  useVoiceState,
} from "../../hooks/useEyloStore";
import { useMessageActions, useVoiceActions } from "../../hooks/useActions";
import { useScrollBehavior } from "../../hooks/useScrollBehavior";
import { useVoiceSystemState } from "../../hooks/useVoiceSystemState";
import { useAgentStatus, type Feedback } from "../../hooks/useAgentStatus";
import { useMessageFeedback } from "../../hooks/useMessageFeedback";
import { useNavigate, useRouteParams } from "../../library/MemoryRouter";
import { useEyloSDK } from "../../main";
import AudioOutput from "../AudioOutput/AudioOutput";
import ChatWidgetContainer from "../ChatWidgetContainer";
import { DynamicWidgetRenderer, InvalidDynamicWidgetPayload } from "../DynamicWidget";
import { WidgetResponseSummary } from "../DynamicWidget/WidgetResponseSummary";
import MessageInput from "../MessageInput";
import MessageContent from "../MessageContent";
import KnowledgeUploadDialog, { type KnowledgeUploadStatus } from "../KnowledgeUploadDialog";
import DinoLoader from "../DinoLoader";
import NewMessagesIndicator from "./NewMessagesIndicator";
import type {
  TKnowledgeIngestion,
  TMessageWParticipant,
  TWidgetInteraction,
  TWidgetResponseData,
} from "@eylo";
import VoiceWaveform from "../VoiceWaveform";
import { VoiceStartUnavailableError } from "@eylo/modules/voice/browser-capabilities";
import { VoiceStartCancelledError } from "@eylo/modules/voice/service";
import { Button } from "../../design-system/components/Button";
import { Empty } from "../../design-system/components/Empty";
import { Text } from "../../design-system/components/Typography";
import { Flex } from "../../design-system/components/Flex";
import { formatMessageTimestamp } from "../../utils";
import styles from "./ConversationDetails.module.css";

// VoiceSystemState type is moved to useVoiceSystemState hook
// getVoiceSystemStatus helper is moved to VoiceStatusPanel component

const TERMINAL_INGESTION_STATES = new Set(["succeeded", "failed", "cancelled"]);

const ConversationDetails: FC<{
  conversationId?: string;
  allowNavigation?: boolean;
}> = ({ conversationId, allowNavigation = true }) => {
  // TEMPORARY: Force show voice panel for debugging/styling
  const DEBUG_SHOW_VOICE_PANEL = false;

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { eyloSDK } = useEyloSDK();
  const navigate = useNavigate();
  const params = useRouteParams();
  const navigateBack = allowNavigation ? () => navigate(PATHS.CONVERSATION_LIST) : undefined;

  // Use conversationId prop if provided (voice mode), otherwise use params.id (text mode)
  const activeConversationId = conversationId || params.id;

  // Action hooks
  const {
    sendMessage: sendMessageAction,
    sendFeedback: sendFeedbackAction,
    sendWidgetResponse: sendWidgetResponseAction,
  } = useMessageActions();
  const { startVoiceSession, stopVoiceSession } = useVoiceActions();

  // Data hooks
  const { isConnected } = useConnectionStatus();
  const conversation = useConversation(undefined, activeConversationId);
  const {
    messages,
    loading,
    error: messagesError,
    loadingMore,
    hasMore,
    loadMore,
    isLoadingMoreRef,
  } = useConversationMessages(undefined, activeConversationId);
  const { isSessionActive, remoteStream, localStream } = useVoiceState();
  const isVoiceActive = isSessionActive;

  const filteredMessages = useMemo(() => {
    return messages.filter((message) => message.kind === "USER" || message.kind === "ASSISTANT");
  }, [messages]);
  const lastMessage =
    filteredMessages.length > 0 ? filteredMessages[filteredMessages.length - 1] : null;

  useEffect(() => {
    if (!activeConversationId || loading) {
      return;
    }
    eyloSDK.conversationService.markRead(activeConversationId);
  }, [activeConversationId, eyloSDK, lastMessage?.id, loading]);

  // Custom hooks for complex logic
  const scrollBehavior = useScrollBehavior({
    messages,
    isLoadingMore: isLoadingMoreRef?.current,
  });

  const { voiceSystemState, canUserSpeak, voiceState } = useVoiceSystemState({
    eyloSDK,
    isVoiceActive: isSessionActive ?? false,
  });

  const { agentStatus, isAgentThinking, setAgentStatus, setIsAgentThinking } = useAgentStatus({
    eyloSDK,
    conversationId: activeConversationId,
  });

  const { selectedFeedback } = useMessageFeedback({
    lastMessage,
    filteredMessages,
  });

  // Local state
  const [message, setMessage] = useState("");
  const [optimisticWidgetResponses, setOptimisticWidgetResponses] = useState<
    Record<string, TWidgetResponseData>
  >({});
  const [knowledgeDialogOpen, setKnowledgeDialogOpen] = useState(false);
  const [knowledgeUploadAllowed, setKnowledgeUploadAllowed] = useState(false);
  const [selectedKnowledgeFile, setSelectedKnowledgeFile] = useState<File | null>(null);
  const [knowledgeUploading, setKnowledgeUploading] = useState(false);
  const [knowledgeIngestion, setKnowledgeIngestion] = useState<TKnowledgeIngestion | null>(null);
  const [knowledgeError, setKnowledgeError] = useState<string | null>(null);

  useEffect(() => {
    setOptimisticWidgetResponses({});
  }, [activeConversationId]);

  useEffect(() => {
    let active = true;
    setKnowledgeUploadAllowed(false);
    setKnowledgeDialogOpen(false);
    setSelectedKnowledgeFile(null);
    setKnowledgeIngestion(null);
    setKnowledgeError(null);

    if (!eyloSDK || !isConnected || !activeConversationId) {
      return;
    }

    eyloSDK.knowledgeService
      .getUploadCapability(activeConversationId)
      .then((capability) => {
        if (active) {
          setKnowledgeUploadAllowed(capability.allowed);
        }
      })
      .catch(() => {
        if (active) {
          setKnowledgeUploadAllowed(false);
        }
      });

    return () => {
      active = false;
    };
  }, [activeConversationId, eyloSDK, isConnected]);

  useEffect(() => {
    if (!eyloSDK || !activeConversationId || !knowledgeIngestion) {
      return;
    }
    if (TERMINAL_INGESTION_STATES.has(knowledgeIngestion.state)) {
      return;
    }

    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const receipt = knowledgeIngestion;

    const poll = async () => {
      try {
        const current = await eyloSDK.knowledgeService.getIngestion(
          activeConversationId,
          receipt.jobId
        );
        if (!active) {
          return;
        }
        setKnowledgeError(null);
        setKnowledgeIngestion(current);
        if (!TERMINAL_INGESTION_STATES.has(current.state)) {
          timer = setTimeout(poll, 1_000);
        }
      } catch (error: unknown) {
        if (!active) {
          return;
        }
        setKnowledgeError(
          error instanceof Error ? error.message : "Could not read Knowledge ingestion status."
        );
        timer = setTimeout(poll, 1_000);
      }
    };

    timer = setTimeout(poll, 1_000);
    return () => {
      active = false;
      if (timer) {
        clearTimeout(timer);
      }
    };
  }, [activeConversationId, eyloSDK, knowledgeIngestion?.jobId]);

  // All agent status, feedback, voice system, and scroll behavior logic
  // has been extracted to custom hooks above

  // Auto-end voice session when navigating away
  useEffect(() => {
    return () => {
      if (eyloSDK.voiceService.hasActiveSession()) {
        stopVoiceSession().catch((err) =>
          console.error("[ConversationDetails] Error stopping voice on unmount:", err)
        );
      }
    };
  }, [eyloSDK, stopVoiceSession]);

  const isDisabled = isAgentThinking || !conversation || loading;

  const handleSendMessage = () => {
    // Guard clause uses the primitive states directly to avoid stale closures
    if (!message.trim() || !conversation || loading || isAgentThinking) {
      return;
    }

    const isSent = sendMessageAction(
      {
        conversationId: conversation.id, // non-null is guaranteed by guard clause
        text: message,
      },
      crypto.randomUUID()
    );

    if (!isSent) {
      setAgentStatus({
        type: "error",
        message: "Cannot send message. Please check your connection.",
      });
      setIsAgentThinking(false);
    }

    // Clear message and reset textarea height
    setMessage("");
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }

    // Scroll to bottom using scroll behavior hook
    scrollBehavior.scrollToBottom();
  };

  const handleKnowledgeUpload = async () => {
    if (!eyloSDK || !activeConversationId || !selectedKnowledgeFile || knowledgeUploading) {
      return;
    }

    setKnowledgeUploading(true);
    setKnowledgeError(null);
    setKnowledgeIngestion(null);
    try {
      const receipt = await eyloSDK.knowledgeService.uploadFile(
        activeConversationId,
        selectedKnowledgeFile
      );
      setKnowledgeIngestion(receipt);
    } catch (error: unknown) {
      setKnowledgeError(
        error instanceof Error ? error.message : "Could not upload Knowledge file."
      );
    } finally {
      setKnowledgeUploading(false);
    }
  };

  const knowledgeBusy =
    knowledgeUploading ||
    Boolean(knowledgeIngestion && !TERMINAL_INGESTION_STATES.has(knowledgeIngestion.state));
  const knowledgeStatus: KnowledgeUploadStatus | null = knowledgeError
    ? { kind: "error", message: knowledgeError }
    : knowledgeUploading
      ? { kind: "progress", message: `Uploading ${selectedKnowledgeFile?.name || "file"}...` }
      : knowledgeIngestion?.state === "succeeded"
        ? {
            kind: "success",
            message: `${knowledgeIngestion.title || "File"} is ready for this conversation.`,
          }
        : knowledgeIngestion?.state === "failed" || knowledgeIngestion?.state === "cancelled"
          ? {
              kind: "error",
              message:
                knowledgeIngestion.lastError ||
                `${knowledgeIngestion.title || "File"} could not be indexed.`,
            }
          : knowledgeIngestion
            ? {
                kind: "progress",
                message: `Indexing ${knowledgeIngestion.title || "file"}...`,
              }
            : null;

  const handleKeyDown = (e: KeyboardEvent) => {
    if (isDisabled) return;

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFeedbackClick = async (feedbackType: "positive" | "negative") => {
    if (!lastMessage?.requestId || selectedFeedback === feedbackType) {
      return;
    }

    sendFeedbackAction(lastMessage.conversationId, lastMessage.requestId, feedbackType);
  };

  const widgetResponsesByMessageId = useMemo(() => {
    const responses = new Map<string, TWidgetResponseData>();

    Object.entries(optimisticWidgetResponses).forEach(([messageId, response]) => {
      responses.set(messageId, response);
    });

    if (!eyloSDK) {
      return responses;
    }

    messages.forEach((currentMessage) => {
      const response = eyloSDK.messageService.getWidgetResponseData(currentMessage);
      if (response) {
        responses.set(response.widget_message_id, response);
      }
    });

    return responses;
  }, [eyloSDK, messages, optimisticWidgetResponses]);

  const handleWidgetInteraction = (widgetMessageId: string, interaction: TWidgetInteraction) => {
    if (!activeConversationId) {
      return;
    }

    const requestId = crypto.randomUUID();
    const response: TWidgetResponseData = {
      type: "widget_response",
      widget_message_id: widgetMessageId,
      component: interaction.component,
      action: interaction.action,
      data: interaction.data,
    };

    const isSent = sendWidgetResponseAction(
      {
        conversationId: activeConversationId,
        widgetMessageId,
        component: interaction.component,
        action: interaction.action,
        data: interaction.data,
      },
      requestId
    );

    if (isSent) {
      setOptimisticWidgetResponses((previous) => ({
        ...previous,
        [widgetMessageId]: response,
      }));
    }
  };

  const handleVoiceToggle = async () => {
    if (!conversation) return;

    const hasActiveVoiceSession = eyloSDK.voiceService.hasActiveSession();
    if (hasActiveVoiceSession) {
      // End voice session
      await stopVoiceSession();
    } else {
      // Start voice session
      setAgentStatus(null); // Clear any previous error status
      try {
        await startVoiceSession(conversation.id);
      } catch (e) {
        if (!(e instanceof VoiceStartCancelledError)) {
          console.error("Failed to start voice session:", e);
          setAgentStatus({
            type: "error",
            message:
              e instanceof VoiceStartUnavailableError
                ? e.message
                : "Voice could not start. Check microphone access and try again.",
          });
        }
      }
    }
  };

  if (!params.id) {
    return (
      <>
        <ChatWidgetContainer.ChatHeader title="No Conversation Selected" onBack={navigateBack} />
        <ChatWidgetContainer.ChatContent>
          <div className={styles.emptyStateContainer}>
            <Empty
              icon={<FaRegComments aria-hidden="true" />}
              title="No Conversation Selected"
              description="Please select a conversation to start chatting"
            />
          </div>
        </ChatWidgetContainer.ChatContent>
      </>
    );
  }

  const handleRetry = () => {
    const lastUserMessage = [...filteredMessages].reverse().find((m) => m.kind === "USER");
    const lastUserMessageText = lastUserMessage
      ? eyloSDK.messageService.getMessageContent(lastUserMessage)
      : null;

    if (lastUserMessageText && conversation) {
      const requestId = crypto.randomUUID();
      sendMessageAction(
        {
          conversationId: conversation.id,
          text: lastUserMessageText,
        },
        requestId
      );
      setAgentStatus(null); // Clear the error message
      setIsAgentThinking(true);
    }
  };

  if (!conversation && !loading) {
    return (
      <>
        <ChatWidgetContainer.ChatHeader title="Conversation Not Found" onBack={navigateBack} />
        <ChatWidgetContainer.ChatContent>
          {loading && <div className={styles.loadingMessage}>Loading messages...</div>}
          {messagesError && (
            <div className={styles.errorMessage}>Error: {messagesError.message}</div>
          )}
          <div className={styles.emptyStateContainer}>
            <Empty
              icon={<FaSearch aria-hidden="true" />}
              title="Conversation Not Found"
              description="The conversation you're looking for doesn't exist"
            />
          </div>
        </ChatWidgetContainer.ChatContent>
      </>
    );
  }

  return (
    <>
      <ChatWidgetContainer.ChatHeader
        title={conversation?.title || "Chat"}
        onBack={navigateBack}
        agentStatus={agentStatus}
      />

      <ChatWidgetContainer.ChatContent>
        <div className={styles.messagesContainer} ref={scrollBehavior.messagesContainerRef}>
          {loading ? (
            <div className={styles.loadingMessage}>Loading messages...</div>
          ) : filteredMessages.length === 0 ? (
            <div className={styles.emptyStateContainer}>
              <Empty
                icon={<FaRegComments aria-hidden="true" />}
                title="Start a new conversation"
                description="Send a message to begin chatting"
              />
            </div>
          ) : (
            <>
              {/* Load More Messages Button */}
              {hasMore && (
                <div className={styles.loadMoreRow}>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={loadMore}
                    disabled={loadingMore}
                    width="full"
                  >
                    {loadingMore ? (
                      <Flex align="center" gap="xs">
                        <span className={styles.loadingIcon}>
                          <RiRefreshLine />
                        </span>
                        <Text size="small">Loading older messages...</Text>
                      </Flex>
                    ) : (
                      <Text size="small">Load older messages</Text>
                    )}
                  </Button>
                </div>
              )}
              {filteredMessages.map((message, index) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  isLastMessage={index === filteredMessages.length - 1}
                  selectedFeedback={selectedFeedback}
                  onFeedbackClick={handleFeedbackClick}
                  agentStatus={agentStatus}
                  handleRetry={handleRetry}
                  onWidgetInteraction={handleWidgetInteraction}
                  widgetSubmission={widgetResponsesByMessageId.get(message.id) ?? null}
                />
              ))}
            </>
          )}
          <div ref={scrollBehavior.messagesEndRef} />
        </div>

        {/* New Messages Indicator */}
        <NewMessagesIndicator
          show={scrollBehavior.showNewMessagesIndicator}
          onClick={scrollBehavior.scrollToBottom}
        />
      </ChatWidgetContainer.ChatContent>

      {/* Unified footer with inline voice/text controls */}
      <ChatWidgetContainer.ChatFooter>
        {isVoiceActive || DEBUG_SHOW_VOICE_PANEL ? (
          <div className={styles.voiceInlineControls}>
            <div className={styles.voiceControlsRow}>
              <Button
                variant="destructive"
                size="icon"
                onClick={handleVoiceToggle}
                aria-label="Stop voice"
              >
                <FaStop size={16} />
              </Button>
              <VoiceWaveform
                voiceSystemState={voiceSystemState}
                status={voiceState}
                localStream={localStream}
                isActive={
                  canUserSpeak && (voiceState === "listening" || voiceState === "connected")
                }
              />
            </div>
          </div>
        ) : (
          /* Text mode with mic button */
          <MessageInput
            inputRef={inputRef}
            value={message}
            onChange={(value) => setMessage(value)}
            onSend={handleSendMessage}
            onKeyDown={handleKeyDown}
            onVoiceToggle={handleVoiceToggle}
            isVoiceActive={false}
            onKnowledgeUpload={
              knowledgeUploadAllowed ? () => setKnowledgeDialogOpen(true) : undefined
            }
            knowledgeUploadDisabled={!isConnected}
            knowledgeUploadBusy={knowledgeBusy}
            disabled={!isConnected || loading || isAgentThinking}
            placeholder={
              !conversation
                ? "Loading conversation..."
                : isAgentThinking
                  ? "Agent is thinking..."
                  : "Type your message..."
            }
          />
          /* Voice mode - inline controls */
        )}
        <DinoLoader visible={isAgentThinking} />
      </ChatWidgetContainer.ChatFooter>

      {/* Audio output for voice */}
      {remoteStream && <AudioOutput stream={remoteStream} />}

      <KnowledgeUploadDialog
        open={knowledgeDialogOpen}
        selectedFile={selectedKnowledgeFile}
        busy={knowledgeBusy}
        status={knowledgeStatus}
        onOpenChange={setKnowledgeDialogOpen}
        onFileChange={(file) => {
          setSelectedKnowledgeFile(file);
          setKnowledgeIngestion(null);
          setKnowledgeError(null);
        }}
        onUpload={handleKnowledgeUpload}
      />
    </>
  );
};

// Message component — memoized to prevent re-rendering all bubbles when
// parent state changes (e.g. isAgentThinking flipping). Without memo,
// dangerouslySetInnerHTML causes Preact to replace the entire DOM subtree
// on every render, producing a visible flash across all messages.
const MessageBubble = memo<{
  message: TMessageWParticipant;
  isLastMessage: boolean;
  selectedFeedback: "positive" | "negative" | null;
  onFeedbackClick: (feedbackType: "positive" | "negative") => void;
  agentStatus: Feedback;
  handleRetry: () => void;
  onWidgetInteraction: (widgetMessageId: string, interaction: TWidgetInteraction) => void;
  widgetSubmission: TWidgetResponseData | null;
}>(
  ({
    message,
    isLastMessage,
    selectedFeedback,
    onFeedbackClick,
    agentStatus,
    handleRetry,
    onWidgetInteraction,
    widgetSubmission,
  }) => {
    const isUser = message.kind === "USER";
    const senderName = message.contact?.name || message.senderParticipant?.entityKind || "Unknown";
    const timestamp = formatMessageTimestamp(message.createdAt);
    const messageContent = useMessageContent(message);
    const widgetPayload = useWidgetMessagePayload(message);
    const widgetResponseData = useWidgetResponseData(message);

    return (
      <div className={styles.messageBubbleContainer}>
        <div
          className={`${styles.messageBubbleRow} ${isUser ? styles.messageBubbleRowUser : styles.messageBubbleRowBot}`}
        >
          <div className={styles.messageBubbleWrapper}>
            <div
              className={`${styles.messageBubbleMeta} ${isUser ? styles.messageBubbleMetaUser : styles.messageBubbleMetaBot}`}
            >
              <Text as="span" size="xs" semibold className={styles.messageBubbleMetaSender}>
                {senderName}
              </Text>
              <Text as="span" size="xs">
                {timestamp}
              </Text>
            </div>
            <div
              className={`${styles.messageBubbleContent} ${isUser ? styles.messageBubbleContentUser : styles.messageBubbleContentBot}`}
            >
              {message.contentKind === "WIDGET" ? (
                widgetPayload?.ok ? (
                  <DynamicWidgetRenderer
                    payload={widgetPayload.value}
                    onInteraction={(interaction) => onWidgetInteraction(message.id, interaction)}
                    isReadOnly={Boolean(widgetSubmission)}
                    submission={widgetSubmission}
                  />
                ) : (
                  <InvalidDynamicWidgetPayload issues={widgetPayload?.issues ?? []} />
                )
              ) : message.contentKind === "WIDGET_RESPONSE" && widgetResponseData ? (
                <WidgetResponseSummary response={widgetResponseData} />
              ) : (
                <MessageContent content={messageContent || ""} className="" />
              )}
            </div>
          </div>
        </div>
        {isLastMessage && message.kind === "ASSISTANT" && (
          <div className={styles.feedbackRow}>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onFeedbackClick("positive")}
              aria-label="Good response"
              disabled={selectedFeedback === "positive"}
              className={`${styles.feedbackButtonActive} ${selectedFeedback === "positive" ? styles.feedbackButtonPositive : styles.feedbackButtonInactive}`}
            >
              {selectedFeedback === "positive" ? (
                <FaThumbsUp size={14} />
              ) : (
                <FaRegThumbsUp size={14} />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onFeedbackClick("negative")}
              aria-label="Bad response"
              disabled={selectedFeedback === "negative"}
              className={`${styles.feedbackButtonActive} ${selectedFeedback === "negative" ? styles.feedbackButtonNegative : styles.feedbackButtonInactive}`}
            >
              {selectedFeedback === "negative" ? (
                <FaThumbsDown size={14} />
              ) : (
                <FaRegThumbsDown size={14} />
              )}
            </Button>
          </div>
        )}
        {isLastMessage && message.kind === "USER" && agentStatus?.showRetry && (
          <div className={styles.retryRow}>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRetry}
              aria-label="Retry"
              className={styles.retryButton}
            >
              <RiRefreshLine size={14} />
              <Text as="span" size="small">
                Retry
              </Text>
            </Button>
          </div>
        )}
      </div>
    );
  }
);

export default ConversationDetails;
