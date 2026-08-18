// hooks/useActions.ts
import type { TMessageCreate, TWidgetResponseMessageCreate } from "@eylo";
import type { TConversationCreate } from "@eylo/modules/conversation";
import { useCallback } from "preact/hooks";
import { useEyloSDK, useEyloServices } from "../main";

/**
 * Hook for message actions
 *
 * Provides methods to send messages and feedback without direct SDK access
 */
export function useMessageActions() {
  const { message } = useEyloServices();

  const sendMessage = useCallback(
    (data: TMessageCreate, requestId: string) => {
      return message.sendMessage(data, requestId);
    },
    [message]
  );

  const sendFeedback = useCallback(
    (conversationId: string, requestId: string, feedback: "positive" | "negative") => {
      return message.sendFeedback(conversationId, requestId, feedback);
    },
    [message]
  );

  const sendWidgetResponse = useCallback(
    (data: TWidgetResponseMessageCreate, requestId: string) => {
      return message.sendWidgetResponse(data, requestId);
    },
    [message]
  );

  return { sendMessage, sendFeedback, sendWidgetResponse };
}

/**
 * Hook for conversation actions
 *
 * Provides methods to start conversations and load messages
 */
export function useConversationActions() {
  const { conversation } = useEyloServices();

  const startConversation = useCallback(
    (data: TConversationCreate, requestId: string) => {
      conversation.startConversation(data, requestId);
    },
    [conversation]
  );

  const loadMoreMessages = useCallback(
    (conversationId: string, limit: number, offset: number) =>
      conversation.loadMoreMessages(conversationId, limit, offset),
    [conversation]
  );

  return { startConversation, loadMoreMessages };
}

/**
 * Hook for voice actions
 *
 * Provides methods to start and stop voice sessions
 */
export function useVoiceActions() {
  const { eyloSDK } = useEyloSDK();

  const startVoiceSession = useCallback(
    async (conversationId: string) => {
      return await eyloSDK.voiceService.startVoiceSession(conversationId);
    },
    [eyloSDK]
  );

  const stopVoiceSession = useCallback(async () => {
    return await eyloSDK.voiceService.endVoiceCall();
  }, [eyloSDK]);

  return { startVoiceSession, stopVoiceSession };
}

/**
 * Hook for agent actions
 *
 * Provides methods to interact with agent data
 */
export function useAgentActions() {
  const { eyloSDK } = useEyloSDK();

  const fetchAgentIntegrations = useCallback(
    async (agentId: string) => {
      return await eyloSDK.agentService.fetchAgentIntegrations(agentId);
    },
    [eyloSDK]
  );

  const fetchBulkAgentIntegrations = useCallback(
    async (agentIds: string[]) => {
      return await eyloSDK.agentService.fetchBulkAgentIntegrations(agentIds);
    },
    [eyloSDK]
  );

  return { fetchAgentIntegrations, fetchBulkAgentIntegrations };
}

/**
 * Hook for widget actions
 *
 * Provides methods to control widget visibility
 */
export function useWidgetActions() {
  const { eyloSDK } = useEyloSDK();

  const openWidget = useCallback(() => {
    eyloSDK.ee.emit("eylo:widget:opened");
  }, [eyloSDK]);

  const closeWidget = useCallback(() => {
    eyloSDK.ee.emit("eylo:widget:closed");
  }, [eyloSDK]);

  return { openWidget, closeWidget };
}
