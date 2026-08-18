// hooks/useScrollBehavior.ts
import { useEffect, useRef, useState } from "preact/hooks";

interface UseScrollBehaviorOptions {
  messages: any[];
  isLoadingMore?: boolean;
}

interface UseScrollBehaviorReturn {
  messagesEndRef: React.RefObject<HTMLDivElement>;
  messagesContainerRef: React.RefObject<HTMLDivElement>;
  isNearBottom: boolean;
  showNewMessagesIndicator: boolean;
  scrollToBottom: () => void;
  hideNewMessagesIndicator: () => void;
}

/**
 * Custom hook to handle scroll behavior in conversation view
 *
 * Features:
 * - Track if user is near bottom of messages
 * - Auto-scroll on initial load
 * - Auto-scroll on new messages (only if user is at bottom)
 * - Show "new messages" indicator when user scrolls up
 * - Preserve scroll position when loading older messages
 */
export function useScrollBehavior({
  messages,
  isLoadingMore,
}: UseScrollBehaviorOptions): UseScrollBehaviorReturn {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [showNewMessagesIndicator, setShowNewMessagesIndicator] = useState(false);

  const previousMessageCountRef = useRef(0);
  const hasScrolledInitiallyRef = useRef(false);

  // Track scroll position to determine if user is near bottom
  useEffect(() => {
    const container = messagesContainerRef.current;

    if (!container) {
      return;
    }

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      // Consider "near bottom" if within 100px of the bottom
      const nearBottom = distanceFromBottom < 100;
      setIsNearBottom(nearBottom);

      // Hide new messages indicator when user scrolls to bottom
      if (nearBottom) {
        setShowNewMessagesIndicator(false);
      }
    };

    container.addEventListener("scroll", handleScroll);

    return () => {
      container.removeEventListener("scroll", handleScroll);
    };
  }, []);

  // Auto-scroll to bottom on initial load and when NEW messages arrive (only if user is at bottom)
  useEffect(() => {
    // Don't auto-scroll if we're loading older messages
    if (isLoadingMore) {
      previousMessageCountRef.current = messages.length;
      return;
    }

    // Auto-scroll on initial load OR when new messages arrive (if user is at bottom)
    if (messagesEndRef.current && messages.length > 0) {
      // Initial load: scroll immediately
      if (!hasScrolledInitiallyRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: "instant" });
        hasScrolledInitiallyRef.current = true;
        setIsNearBottom(true);
      }
      // New messages arrived
      else if (
        previousMessageCountRef.current > 0 &&
        messages.length > previousMessageCountRef.current
      ) {
        if (isNearBottom) {
          // User is at bottom, auto-scroll
          messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
        } else {
          // User has scrolled up - show indicator
          setShowNewMessagesIndicator(true);
        }
      }
    }

    previousMessageCountRef.current = messages.length;
  }, [messages, isNearBottom, isLoadingMore]);

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
      setIsNearBottom(true);
      setShowNewMessagesIndicator(false);
    }
  };

  const hideNewMessagesIndicator = () => {
    setShowNewMessagesIndicator(false);
  };

  return {
    messagesEndRef,
    messagesContainerRef,
    isNearBottom,
    showNewMessagesIndicator,
    scrollToBottom,
    hideNewMessagesIndicator,
  };
}
