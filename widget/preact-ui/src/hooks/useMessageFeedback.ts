// hooks/useMessageFeedback.ts
import type { TMessageWParticipant } from "@eylo";

interface UseMessageFeedbackOptions {
  lastMessage: TMessageWParticipant | null;
  filteredMessages: TMessageWParticipant[];
}

interface UseMessageFeedbackReturn {
  selectedFeedback: "positive" | "negative" | null;
}

/**
 * Custom hook to manage message feedback state
 *
 * Automatically syncs feedback state with the last message's feedback
 */
export function useMessageFeedback({
  lastMessage,
  filteredMessages,
}: UseMessageFeedbackOptions): UseMessageFeedbackReturn {
  const userMessageForRequest = filteredMessages.find(
    (message) =>
      message.kind === "USER" &&
      Boolean(lastMessage?.requestId) &&
      message.requestId === lastMessage?.requestId
  );
  const requestFeedback = userMessageForRequest?.requestFeedback?.toLowerCase();
  const selectedFeedback =
    requestFeedback === "positive" || requestFeedback === "negative"
      ? requestFeedback
      : null;

  return {
    selectedFeedback,
  };
}
