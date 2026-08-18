// hooks/useIsAgentWorking.ts
import { useEffect, useState } from "preact/hooks";
import { useEyloSDK } from "../main";
import { agentStatusStore } from "../stores/agentStatusStore";

/**
 * Hook to check if agent is actively working on a conversation
 *
 * Uses global store so status persists across navigation
 */
export function useIsAgentWorking(conversationId: string | undefined): boolean {
  const { eyloSDK } = useEyloSDK();
  const [isWorking, setIsWorking] = useState(false);

  // Initialize store with SDK
  useEffect(() => {
    if (eyloSDK) {
      agentStatusStore.initialize(eyloSDK);
    }
  }, [eyloSDK]);

  // Subscribe to store and get status
  useEffect(() => {
    if (!conversationId) {
      setIsWorking(false);
      return;
    }

    // Get current status from store (real backend data only)
    setIsWorking(agentStatusStore.isWorking(conversationId));

    // Subscribe to changes
    const unsubscribe = agentStatusStore.subscribe(() => {
      setIsWorking(agentStatusStore.isWorking(conversationId));
    });

    return unsubscribe;
  }, [conversationId]);

  return isWorking;
}
