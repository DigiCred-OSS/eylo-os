// hooks/useEyloAdvanced.ts
import { useCallback, useEffect, useState } from "preact/hooks";

import { useEyloSDK } from "../main";
import { logger } from "../utils";

/**
 * Hook for optimistic updates
 */
export function useOptimisticMessage() {
  const { eyloSDK } = useEyloSDK();
  const [optimisticMessages, setOptimisticMessages] = useState<Map<string, any>>(new Map());

  const sendOptimisticMessage = useCallback(
    (conversationId: string, text: string) => {
      const tempId = `temp-${Date.now()}`;
      const requestId = crypto.randomUUID();

      // Create optimistic message
      const optimisticMessage = {
        id: tempId,
        conversationId,
        content: text,
        kind: "USER",
        contentKind: "TEXT",
        createdAt: new Date().toISOString(),
        senderParticipant: { entityKind: "CONTACT" },
        _isOptimistic: true,
        _requestId: requestId,
      };

      // Add to optimistic messages
      setOptimisticMessages((prev) => {
        const next = new Map(prev);
        next.set(requestId, optimisticMessage);
        return next;
      });

      // Send actual message
      eyloSDK?.sendMessage({ conversationId, text }, requestId);

      return requestId;
    },
    [eyloSDK]
  );

  // Listen for actual message creation to remove optimistic version
  useEffect(() => {
    if (!eyloSDK) return;

    const handleMessageCreated = (message: any) => {
      // Check if this is a response to an optimistic message
      setOptimisticMessages((prev) => {
        const next = new Map(prev);
        // Remove optimistic message when real one arrives
        for (const [requestId, optimistic] of next) {
          if (optimistic.conversationId === message.conversationId) {
            next.delete(requestId);
            break;
          }
        }
        return next;
      });
    };

    eyloSDK.ee.on("eylo:message:created", handleMessageCreated);

    return () => {
      eyloSDK.ee.off("eylo:message:created", handleMessageCreated);
    };
  }, [eyloSDK]);

  return {
    sendOptimisticMessage,
    optimisticMessages: Array.from(optimisticMessages.values()),
  };
}

export function useLogger() {
  return {
    logger,
    debug: logger.debug.bind(logger),
    info: logger.info.bind(logger),
    warn: logger.warn.bind(logger),
    error: logger.error.bind(logger),
    group: logger.group.bind(logger),
    groupEnd: logger.groupEnd.bind(logger),
    time: logger.time.bind(logger),
    timeEnd: logger.timeEnd.bind(logger),
  };
}
