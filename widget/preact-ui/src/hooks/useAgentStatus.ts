// hooks/useAgentStatus.ts
import type { Eylo } from "@eylo/sdk/Eylo";
import type { VNode } from "preact";
import { useEffect, useState } from "preact/hooks";
import { agentStatusStore } from "../stores/agentStatusStore";

export type Feedback = {
  message: string;
  type: "info" | "error";
  showRetry?: boolean;
  icon?: VNode;
  statusType?: "thinking" | "processing" | "tool_executing" | "tool_completed";
} | null;

interface UseAgentStatusOptions {
  eyloSDK: Eylo | undefined;
  conversationId: string | undefined;
}

interface UseAgentStatusReturn {
  agentStatus: Feedback;
  isAgentThinking: boolean;
  setAgentStatus: (status: Feedback) => void;
  setIsAgentThinking: (thinking: boolean) => void;
}

/**
 * Custom hook to manage agent status updates and thinking state
 *
 * Now uses global agentStatusStore to maintain state across navigation
 */
export function useAgentStatus({
  eyloSDK,
  conversationId,
}: UseAgentStatusOptions): UseAgentStatusReturn {
  const [agentStatus, setAgentStatus] = useState<Feedback>(null);
  const [isAgentThinking, setIsAgentThinking] = useState(false);

  // Initialize global store
  useEffect(() => {
    if (eyloSDK) {
      agentStatusStore.initialize(eyloSDK);
    }
  }, [eyloSDK]);

  // Subscribe to store changes for this conversation
  useEffect(() => {
    if (!conversationId) {
      setAgentStatus(null);
      setIsAgentThinking(false);
      return;
    }

    // Get initial status from store
    const status = agentStatusStore.getStatus(conversationId);
    if (status) {
      const isWorking = agentStatusStore.isWorking(conversationId);
      setIsAgentThinking(isWorking);

      if (isWorking) {
        setAgentStatus({
          type: "info",
          message: status.message || "Agent is working...",
          statusType: status.type as any,
        });
      } else if (status.type === "error") {
        setAgentStatus({
          type: "error",
          message: status.message || "The agent could not complete this request.",
          showRetry: true,
        });
      } else {
        setAgentStatus(null);
      }
    }

    // Subscribe to updates
    const unsubscribe = agentStatusStore.subscribe(() => {
      const updatedStatus = agentStatusStore.getStatus(conversationId);
      const isWorking = agentStatusStore.isWorking(conversationId);

      setIsAgentThinking(isWorking);

      if (updatedStatus && isWorking) {
        setAgentStatus({
          type: "info",
          message: updatedStatus.message || "Agent is working...",
          statusType: updatedStatus.type as any,
        });
      } else if (updatedStatus?.type === "error") {
        setAgentStatus({
          type: "error",
          message: updatedStatus.message || "The agent could not complete this request.",
          showRetry: true,
        });
      } else {
        setAgentStatus(null);
      }
    });

    return unsubscribe;
  }, [conversationId]);

  // Listen for global error events to catch message send failures
  useEffect(() => {
    if (!eyloSDK) return;

    const handleError = (error: any) => {
      const errorMessage = error?.data?.message;
      const errorDetails = error?.data?.details;

      const friendlyMessage =
        errorDetails || errorMessage || "Something went wrong. Please try again.";
      setAgentStatus({ type: "error", message: friendlyMessage });
      setIsAgentThinking(false);
    };

    eyloSDK.ee.on("eylo:error", handleError);

    return () => {
      eyloSDK.ee.off("eylo:error", handleError);
    };
  }, [eyloSDK, conversationId]);

  return {
    agentStatus,
    isAgentThinking,
    setAgentStatus,
    setIsAgentThinking,
  };
}
