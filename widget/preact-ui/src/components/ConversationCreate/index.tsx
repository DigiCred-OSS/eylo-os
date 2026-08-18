// components/ConversationCreate/index.tsx
import type { TConversation } from "@eylo/modules/conversation";
import type { TAgent } from "@eylo";
import type { FC } from "preact/compat";
import { useRef, useState } from "preact/hooks";

import { PATHS } from "../../app";
import { useLogger } from "../../hooks/useEyloAdvanced";
import {
  useAgents,
  useConnectionStatus,
  useEyloEvent,
  useCurrentContact,
} from "../../hooks/useEyloStore";
import { useConversationActions, useMessageActions, useVoiceActions } from "../../hooks/useActions";
import { useNavigate, useRouteParams } from "../../library/MemoryRouter";
import { useEyloSDK } from "../../main";
import ChatWidgetContainer from "../ChatWidgetContainer";
import MessageInput from "../MessageInput";
import { Card, CardHeader, CardTitle } from "../../design-system/components/Card";
import { Text } from "../../design-system/components/Typography";
import { Stack } from "../../design-system/components/Stack";
import { Box } from "../../design-system/components/Box";

// Subcomponent: Agent information display
const AgentInfoCard: FC<{ agent: TAgent }> = ({ agent }) => (
  <Card border shadow="none" borderRadius="md">
    <CardHeader>
      <CardTitle>{agent.name}</CardTitle>
      {agent.description && (
        <Text size="small" muted>
          {agent.description}
        </Text>
      )}
    </CardHeader>
  </Card>
);

// Subcomponent: Connection status warning
const ConnectionStatusCard: FC<{ isConnected: boolean }> = ({ isConnected }) => {
  if (isConnected) return null;

  return (
    <Card variant="muted" shadow="sm" borderRadius="sm">
      <Text size="small" muted align="center">
        Not connected. Please wait...
      </Text>
    </Card>
  );
};

type PendingConversationStart =
  | { kind: "text"; message: string; requestId: string }
  | { kind: "voice"; requestId: string };

const ConversationCreate: FC = () => {
  const { debug, error } = useLogger();
  const navigate = useNavigate();
  const params = useRouteParams();
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [message, setMessage] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const pendingStartRef = useRef<PendingConversationStart | null>(null);

  // Use hooks
  const { getById } = useAgents();
  const { isConnected } = useConnectionStatus();
  const contact = useCurrentContact();
  const { startConversation } = useConversationActions();
  const { sendMessage } = useMessageActions();
  const { startVoiceSession } = useVoiceActions();
  const { eyloSDK } = useEyloSDK();
  const sessionContactId = eyloSDK.store.sessionContactId;

  // Derived state
  const isAgentConversation = params.id !== undefined;
  const agent = isAgentConversation && params.id ? getById(params.id) : undefined;

  /**
   * Helper: Build conversation data structure
   * Used for both text and voice conversation creation
   */
  const buildConversationData = () => {
    const contactId = sessionContactId || contact?.id;
    const externalId = contact?.externalId;
    if (!(contactId || externalId) || !params.id) {
      throw new Error("Missing required data: contact or agent ID");
    }

    return {
      from: {
        kind: "CONTACT" as const,
        ...(contactId ? { id: contactId } : { externalId }),
      },
      to: {
        kind: "AGENT" as const,
        id: params.id,
      },
      message: {
        content: [],
      },
      context: {},
    };
  };

  /**
   * Validates prerequisites for conversation creation
   * Returns error message if invalid, null if valid
   */
  const validateConversationCreation = (): string | null => {
    if (!isConnected) return "Not connected to the server";
    if (isCreating) return "Already creating a conversation";
    if (!(sessionContactId || contact?.externalId || contact?.id)) {
      return "Contact is not initialized";
    }
    if (!params.id) return "Agent not found";
    return null;
  };
  /**
   * Event listener: Handle successful conversation creation
   *
   * Flow:
   * 1. Match the response to this component's pending request
   * 2. Start voice, or send the first text through the durable message path
   * 3. Navigate to the created conversation
   */
  useEyloEvent(
    eyloSDK,
    "eylo:conversation:created",
    async (conversation: TConversation, requestId?: string) => {
      const pendingStart = pendingStartRef.current;
      if (!pendingStart || pendingStart.requestId !== requestId) {
        return;
      }
      pendingStartRef.current = null;
      debug("New conversation created:", conversation.id);

      if (pendingStart.kind === "voice") {
        try {
          await startVoiceSession(conversation.id);
        } catch (e) {
          error("Failed to start voice session:", e);
        }
      } else {
        const sent = sendMessage(
          {
            conversationId: conversation.id,
            text: pendingStart.message,
          },
          crypto.randomUUID()
        );
        if (!sent) {
          error("Conversation created, but the first message could not be sent.");
        }
      }

      setMessage("");
      navigate(PATHS.CONVERSATION_DETAILS, { id: conversation.id });
    },
    [sendMessage, startVoiceSession]
  );

  /**
   * Handler: Create conversation with text message
   */
  const handleCreateConversation = async () => {
    const validationError = validateConversationCreation();
    if (validationError) {
      error(validationError);
      return;
    }

    const msg = message.trim();
    if (!msg) return;

    setIsCreating(true);

    try {
      const requestId = crypto.randomUUID();
      pendingStartRef.current = { kind: "text", message: msg, requestId };
      const conversationData = buildConversationData();
      debug("Creating text conversation:", conversationData);
      startConversation(conversationData, requestId);
    } catch (e) {
      pendingStartRef.current = null;
      error("Failed to create conversation:", e);
      setIsCreating(false);
    }
  };

  /**
   * Handler: Keyboard shortcuts
   */
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleCreateConversation();
    } else if (e.key === "Escape") {
      navigate(PATHS.CONVERSATION_LIST);
    }
  };

  /**
   * Handler: Start voice conversation
   *
   * Voice flow:
   * 1. Record the correlated voice request
   * 2. Create conversation without message
   * 3. Event listener picks up creation and starts voice session
   * 4. Navigate to conversation detail page
   */
  const handleVoiceToggle = async () => {
    const validationError = validateConversationCreation();
    if (validationError) {
      error(validationError);
      return;
    }

    setIsCreating(true);

    try {
      const requestId = crypto.randomUUID();
      pendingStartRef.current = { kind: "voice", requestId };
      const conversationData = buildConversationData();
      debug("Creating voice conversation:", conversationData);
      startConversation(conversationData, requestId);
    } catch (e) {
      pendingStartRef.current = null;
      error("Failed to create conversation for voice:", e);
      setIsCreating(false);
    }
  };

  return (
    <>
      <ChatWidgetContainer.ChatHeader
        title="New conversation"
        onBack={() => navigate(PATHS.AGENT_LIST)}
      />

      <ChatWidgetContainer.ChatContent>
        <Box>
          <Stack spacing="md">
            <ConnectionStatusCard isConnected={isConnected} />
            {isAgentConversation && agent && <AgentInfoCard agent={agent} />}
          </Stack>
        </Box>
      </ChatWidgetContainer.ChatContent>

      <ChatWidgetContainer.ChatFooter>
        <MessageInput
          inputRef={inputRef}
          value={message}
          onChange={setMessage}
          onSend={handleCreateConversation}
          onKeyDown={handleKeyDown}
          onVoiceToggle={handleVoiceToggle}
          isVoiceActive={false}
          disabled={isCreating || !isConnected}
          placeholder="Type your message..."
        />
      </ChatWidgetContainer.ChatFooter>
    </>
  );
};

export default ConversationCreate;
