// hooks/useEyloStore.ts
import type { TMessage, TMessageWParticipant } from "@eylo";
import type { BaseReactiveStore } from "@eylo/base/BaseReactiveStore";
import { EYLO_EVENTS, type EventTypes as EyloEvent } from "@eylo/events";
import type { Agent, AgentStore } from "@eylo/modules/agent";
import type { Contact, ContactStore } from "@eylo/modules/contact";
import type { Conversation, ConversationStore } from "@eylo/modules/conversation";
import type { Message } from "@eylo/modules/message/model";
import type { VoiceStore } from "@eylo/modules/voice/store";
import type { ConnectionStore } from "@eylo/net";
import type { Eylo } from "@eylo/sdk";
import { orderBy } from "es-toolkit";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { useEyloSDK } from "../main";

/**
 * Generic hook to subscribe to a specific property in any Eylo store
 */
export function useStoreProperty<T extends Record<string, any>, K extends keyof T>(
  store: BaseReactiveStore<T> | undefined,
  key: K
): T[K] | undefined {
  const [value, setValue] = useState<T[K] | undefined>(() => store?.get(key));
  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!store) {
      setValue(undefined);
      return;
    }

    // Clean up previous subscription
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
    }

    // Subscribe to property changes
    unsubscribeRef.current = store.subscribe(key, (detail) => {
      setValue(detail.value as T[K]);
    });

    // Get current value in case it changed before subscription
    setValue(store.get(key));

    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
    };
  }, [store, key]);

  return value;
}

/**
 * Hook to subscribe to repository list changes
 */
export function useRepositoryList<T extends { id: string }>(
  store:
    | {
        list_: () => T[];
        subscribe: (key: any, cb: () => void) => () => void;
      }
    | undefined,
  itemsListKey: "contacts" | "conversations" | "agents" | "messages" | "participants"
) {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!store) {
      setData([]);
      setLoading(false);
      return;
    }

    const updateItems = () => {
      setError(null);
      try {
        const newItems = store.list_();
        setData(newItems);
      } catch (e: any) {
        console.error(`Failed to list items for key ${String(itemsListKey)}`, e);
        setError(e);
      }
    };

    // Initial fetch
    setLoading(true);
    updateItems();
    setLoading(false);

    // Subscribe to changes
    const unsubscribe = store.subscribe(itemsListKey, updateItems);

    // Cleanup subscription
    return () => {
      unsubscribe();
    };
  }, [store, itemsListKey]);

  return { data, loading, error };
}

/**
 * Hook for connection status
 */
export function useConnectionStatus(connectionStore?: ConnectionStore) {
  const { eyloSDK } = connectionStore ? { eyloSDK: null } : useEyloSDK();
  const store = connectionStore || eyloSDK?.store.cm;

  const isConnected = useStoreProperty(store, "isConnected");
  const sessionId = useStoreProperty(store, "sessionId");
  // 'identified' may not be in the typed ConnectionStore (from @eylo/net) yet; cast safely
  const identified = useStoreProperty(
    (store as unknown as BaseReactiveStore<any>) || undefined,
    "identified" as any
  );
  const error = useStoreProperty(
    (store as unknown as BaseReactiveStore<any>) || undefined,
    "error" as any
  );

  return {
    isConnected: isConnected || false,
    sessionId: sessionId || null,
    identified: identified || false,
    error,
  };
}

/**
 * Hook for contacts
 */
export function useContacts(contactStore: ContactStore | undefined) {
  const { data: contacts, loading, error } = useRepositoryList<Contact>(contactStore, "contacts");

  return {
    contacts,
    loading,
    error,
    getById: (id: string) => contactStore?.get_(id),
    getByExternalId: (externalId: string) => contactStore?.get_byExternalId(externalId),
  };
}

/**
 * Hook for conversations
 */
export function useConversations(eylo?: Eylo) {
  const pageSize = 5;
  const { eyloSDK } = eylo ? { eyloSDK: null } : useEyloSDK();
  const sdk = eylo || eyloSDK;
  const conversationStore = sdk?.store.conversationStore;
  const { isConnected } = useConnectionStatus(sdk?.store.cm);

  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const nextPageRef = useRef(1);
  const loadingMoreRef = useRef(false);

  // This will reactively update when the store changes after the fetch.
  const {
    data: conversations,
    loading: listLoading,
    error: listError,
  } = useRepositoryList<Conversation>(conversationStore, "conversations");

  useEffect(() => {
    // Don't fetch if the SDK isn't ready or we're not connected.
    if (!sdk || !isConnected) {
      setLoading(false);
      return;
    }

    let disposed = false;
    const fetchConversations = async () => {
      setLoading(true);
      setError(null);
      setHasMore(false);
      nextPageRef.current = 1;
      try {
        const itemCount = await sdk.conversationService.listConversations({
          page: 1,
          limit: pageSize,
        });
        if (disposed) {
          return;
        }
        nextPageRef.current = 2;
        setHasMore(itemCount === pageSize);
      } catch (err) {
        if (!disposed) {
          console.error("Failed to fetch conversations:", err);
          setError(err as Error);
        }
      } finally {
        if (!disposed) {
          setLoading(false);
        }
      }
    };

    void fetchConversations();
    return () => {
      disposed = true;
    };
  }, [sdk, isConnected]);

  const loadMore = async () => {
    if (!sdk || !isConnected || !hasMore || loadingMoreRef.current) {
      return;
    }
    loadingMoreRef.current = true;
    setLoadingMore(true);
    setError(null);
    try {
      const itemCount = await sdk.conversationService.listConversations({
        page: nextPageRef.current,
        limit: pageSize,
      });
      nextPageRef.current += 1;
      setHasMore(itemCount === pageSize);
    } catch (err) {
      console.error("Failed to load older conversations:", err);
      setError(err as Error);
    } finally {
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  };

  return {
    conversations,
    loading: listLoading || loading,
    loadingMore,
    hasMore,
    loadMore,
    error: listError || error,
    getById: (id: string) => conversationStore?.get_(id),
    getByExternalId: (externalId: string) => conversationStore?.get_byExternalId(externalId),
    activeConversations: useMemo(
      () =>
        orderBy(
          conversations.filter((conv) => conv.status === "ACTIVE"),
          [(obj) => new Date(obj.updatedAt).getTime()],
          ["desc"]
        ),
      [conversations]
    ),
    completedConversations: useMemo(
      () =>
        orderBy(
          conversations.filter((conv) => conv.status === "COMPLETED"),
          [(obj) => new Date(obj.updatedAt).getTime()],
          ["desc"]
        ),
      [conversations]
    ),
  };
}

/**
 * Hook for messages in a specific conversation with pagination support
 */
export function useConversationMessages(eyloParam?: Eylo, conversationId?: string) {
  const { eyloSDK } = useEyloSDK();
  const eylo = eyloParam || eyloSDK;

  const [messages, setMessages] = useState<TMessageWParticipant[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const messageOffsetRef = useRef(0);
  const totalMessageCountRef = useRef(0);
  const initialLoadedRef = useRef(false);
  const isLoadingMoreRef = useRef(false);
  const activeConversationIdRef = useRef<string | undefined>(conversationId);

  useEffect(() => {
    activeConversationIdRef.current = conversationId;
    if (!eylo || !conversationId) {
      setMessages([]);
      setLoading(false);
      setHasMore(false);
      return;
    }

    let disposed = false;
    setLoading(true);
    setError(null);
    setMessages([]);
    setHasMore(false);
    messageOffsetRef.current = 0;
    totalMessageCountRef.current = 0;
    initialLoadedRef.current = false;
    isLoadingMoreRef.current = false;

    // Subscribe to new messages for this conversation
    const handleNewMessage = (message: Message) => {
      if (message.conversationId === conversationId) {
        // Use the service to resolve the full message with participant info
        const resolvedMessage = eylo.messageService.resolveMessage(message);
        setMessages((current) =>
          mergeConversationMessages(current, [resolvedMessage], conversationId)
        );
      }
    };

    const refreshMessageRelations = () => {
      setMessages((current) =>
        current.map((message) => eylo.messageService.resolveMessage_byId(message.id) ?? message)
      );
    };

    eylo.ee.on(EYLO_EVENTS.MESSAGE_CREATED, handleNewMessage);
    eylo.ee.on(EYLO_EVENTS.MESSAGE_FEEDBACK, handleNewMessage);
    eylo.ee.on(EYLO_EVENTS.MESSAGE_TRANSCRIPT, handleNewMessage);
    const unsubscribeMessageRelations = subscribeToMessageRelations(eylo, refreshMessageRelations);

    const loadInitialPage = async () => {
      try {
        const page = await eylo.conversationService.loadMoreMessages(conversationId, 10, 0);
        if (disposed) {
          return;
        }
        messageOffsetRef.current = page.messages.length;
        totalMessageCountRef.current = page.totalMessageCount;
        initialLoadedRef.current = true;
        setMessages((current) => mergeConversationMessages(current, page.messages, conversationId));
        setHasMore(messageOffsetRef.current < page.totalMessageCount);
      } catch (err) {
        if (!disposed) {
          console.error(`Failed to resolve conversation messages for ${conversationId}:`, err);
          setError(err as Error);
        }
      } finally {
        if (!disposed) {
          setLoading(false);
        }
      }
    };
    void loadInitialPage();

    return () => {
      disposed = true;
      eylo.ee.off(EYLO_EVENTS.MESSAGE_CREATED, handleNewMessage);
      eylo.ee.off(EYLO_EVENTS.MESSAGE_FEEDBACK, handleNewMessage);
      eylo.ee.off(EYLO_EVENTS.MESSAGE_TRANSCRIPT, handleNewMessage);
      unsubscribeMessageRelations();
    };
  }, [eylo, conversationId]);

  const loadMore = async () => {
    if (
      !eylo ||
      !conversationId ||
      isLoadingMoreRef.current ||
      !hasMore ||
      !initialLoadedRef.current
    ) {
      return;
    }

    isLoadingMoreRef.current = true;
    setLoadingMore(true);

    try {
      const messageLimit = 20;
      const page = await eylo.conversationService.loadMoreMessages(
        conversationId,
        messageLimit,
        messageOffsetRef.current
      );
      if (activeConversationIdRef.current !== conversationId) {
        return;
      }
      messageOffsetRef.current += page.messages.length;
      totalMessageCountRef.current = page.totalMessageCount;
      setMessages((current) => mergeConversationMessages(current, page.messages, conversationId));
      setHasMore(
        page.messages.length > 0 && messageOffsetRef.current < totalMessageCountRef.current
      );
    } catch (err) {
      console.error("Failed to load more messages:", err);
      setError(err as Error);
    } finally {
      setLoadingMore(false);
      isLoadingMoreRef.current = false;
    }
  };

  return { messages, loading, error, loadingMore, hasMore, loadMore, isLoadingMoreRef };
}

function mergeConversationMessages(
  current: TMessageWParticipant[],
  incoming: TMessageWParticipant[],
  conversationId: string
): TMessageWParticipant[] {
  const byId = new Map(
    current
      .filter((message) => message.conversationId === conversationId)
      .map((message) => [message.id, message])
  );
  incoming.forEach((message) => {
    if (message.externalId) {
      byId.forEach((existing, id) => {
        if (existing.externalId === message.externalId && id !== message.id) {
          byId.delete(id);
        }
      });
    }
    byId.set(message.id, message);
  });
  return orderBy([...byId.values()], [(message) => new Date(message.createdAt).getTime()], ["asc"]);
}

function subscribeToMessageRelations(eylo: Eylo, refresh: () => void): () => void {
  const unsubscribe = [
    eylo.store.participantStore.subscribe("participants", refresh),
    eylo.store.contactStore.subscribe("contacts", refresh),
    eylo.store.agentStore.subscribe("agents", refresh),
  ];
  return () => unsubscribe.forEach((stop) => stop());
}

/**
 * Hook to listen to Eylo events
 */
export function useEyloEvent(
  eylo: Eylo | undefined,
  eventName: EyloEvent,
  handler: (...args: any[]) => void,
  deps: any[] = []
) {
  const handlerRef = useRef(handler);

  // Update handler ref on each render
  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);

  useEffect(() => {
    if (!eylo) return;

    // Create a stable handler that calls the current handler ref
    const stableHandler = (...args: any[]) => {
      handlerRef.current(...args);
    };

    eylo.ee.on(eventName, stableHandler);

    return () => {
      eylo.ee.off(eventName, stableHandler);
    };
  }, [eylo, eventName, ...deps]);
}

/**
 * Hook to get a specific conversation with reactive updates
 */
export function useConversation(
  conversationStore?: ConversationStore | undefined,
  conversationId?: string | undefined
) {
  const { eyloSDK } = conversationStore ? { eyloSDK: null } : useEyloSDK();
  const store = conversationStore || eyloSDK?.store.conversationStore;

  const [conversation, setConversation] = useState<Conversation | undefined>(() =>
    conversationId ? store?.get_(conversationId) : undefined
  );

  useEffect(() => {
    if (!store || !conversationId) {
      setConversation(undefined);
      return;
    }

    // Get initial conversation
    setConversation(store.get_(conversationId));

    // Subscribe to conversation updates
    const unsubscribe = store.subscribe("conversations", () => {
      const updated = store.get_(conversationId);
      setConversation(updated);
    });

    return unsubscribe;
  }, [store, conversationId]);

  return conversation;
}

/**
 * Hook for agents
 */
export function useAgents(agentStore?: AgentStore) {
  const { eyloSDK } = agentStore ? { eyloSDK: null } : useEyloSDK();
  const store = agentStore || eyloSDK?.store.agentStore;

  const { data: agents, loading, error } = useRepositoryList<Agent>(store, "agents");

  return {
    agents,
    loading,
    error,
    getById: (id: string) => store?.get_(id),
  };
}

/**
 * Hook for voice state
 */
export function useVoiceState(voiceStore?: VoiceStore | undefined) {
  const { eyloSDK } = voiceStore ? { eyloSDK: null } : useEyloSDK();
  const store = voiceStore || eyloSDK?.store.voiceStore;

  const isSessionActive = useStoreProperty(store, "isSessionActive");
  const connectionState = useStoreProperty(store, "connectionState");
  const remoteStream = useStoreProperty(store, "remoteStream");
  const localStream = useStoreProperty(store, "localStream");
  const webrtcState = useStoreProperty(store, "webrtcState");
  const sttState = useStoreProperty(store, "sttState");
  const ttsState = useStoreProperty(store, "ttsState");
  const realtimeState = useStoreProperty(store, "realtimeState");
  const lastError = useStoreProperty(store, "lastError");

  return {
    isSessionActive: isSessionActive ?? false,
    connectionState: connectionState ?? "DISCONNECTED",
    webrtcState: webrtcState ?? null,
    sttState: sttState ?? null,
    ttsState: ttsState ?? null,
    realtimeState: realtimeState ?? "inactive",
    lastError: lastError ?? null,
    remoteStream: remoteStream ?? null,
    localStream: localStream ?? null,
  };
}

/**
 * Hook for current contact
 */
export function useCurrentContact() {
  const { eyloSDK } = useEyloSDK();
  const { contacts } = useContacts(eyloSDK.store.contactStore);
  return contacts[0];
}

/**
 * Hook for connection state manager
 */
export function useConnectionStateManager() {
  const { eyloSDK } = useEyloSDK();
  return useMemo(() => eyloSDK?.store.connectionStateManager, [eyloSDK]);
}

/**
 * Hook for last message of a conversation
 *
 * Note: For agent integrations, use the dedicated useAgentIntegrations hook
 * from hooks/useAgentIntegrations.ts which provides proper type safety,
 * cancellation handling, and filtered data.
 */
export function useLastMessage(conversationId: string | undefined): TMessageWParticipant | null {
  const { eyloSDK } = useEyloSDK();
  const [lastMessage, setLastMessage] = useState<TMessageWParticipant | null>(null);

  useEffect(() => {
    if (!eyloSDK || !conversationId) {
      setLastMessage(null);
      return;
    }

    const initialMessage = eyloSDK.conversationService.getLastMessage(conversationId);
    setLastMessage(initialMessage ?? null);

    // Subscribe to new messages for this conversation
    // Note: The event emits Message model instances, not TMessage types
    const handleNewMessage = (message: any) => {
      if (message.conversationId === conversationId) {
        // resolveMessage expects Message model, converts to TMessageWParticipant
        const updatedMessage = eyloSDK.messageService.resolveMessage(message);
        setLastMessage((current) => {
          if (!current) {
            return updatedMessage;
          }
          return new Date(updatedMessage.createdAt).getTime() >=
            new Date(current.createdAt).getTime()
            ? updatedMessage
            : current;
        });
      }
    };

    const refreshLastMessageRelations = () => {
      setLastMessage((current) => {
        if (!current) {
          return current;
        }
        return eyloSDK.messageService.resolveMessage_byId(current.id) ?? current;
      });
    };

    eyloSDK.ee.on("eylo:message:created", handleNewMessage);
    const unsubscribeMessageRelations = subscribeToMessageRelations(
      eyloSDK,
      refreshLastMessageRelations
    );

    return () => {
      eyloSDK.ee.off("eylo:message:created", handleNewMessage);
      unsubscribeMessageRelations();
    };
  }, [eyloSDK, conversationId]);

  return lastMessage;
}

/**
 * Hook for formatted message content
 *
 * Extracts readable text content from a message, handling different message types
 * (USER, ASSISTANT, SYSTEM, TOOL_USE, TOOL_RESULT)
 */
export function useMessageContent(message: TMessage | TMessageWParticipant | undefined | null) {
  const { eyloSDK } = useEyloSDK();

  return useMemo(() => {
    if (!eyloSDK || !message) return null;
    return eyloSDK.messageService.getMessageContent(message);
  }, [eyloSDK, message]);
}

export function useWidgetMessagePayload(
  message: TMessage | TMessageWParticipant | undefined | null
) {
  const { eyloSDK } = useEyloSDK();

  return useMemo(() => {
    if (!eyloSDK || !message || message.contentKind !== "WIDGET") {
      return null;
    }

    return eyloSDK.messageService.getWidgetPayload(message);
  }, [eyloSDK, message]);
}

/**
 * Hook for plain text message content
 *
 * Returns plain text content from a message, stripping HTML from USER and ASSISTANT messages
 */
export function useWidgetResponseData(message: TMessage | TMessageWParticipant | undefined | null) {
  const { eyloSDK } = useEyloSDK();

  return useMemo(() => {
    if (!eyloSDK || !message || message.contentKind !== "WIDGET_RESPONSE") {
      return null;
    }
    return eyloSDK.messageService.getWidgetResponseData(message);
  }, [eyloSDK, message]);
}

export function useMessageContentPlainText(
  message: TMessage | TMessageWParticipant | undefined | null
) {
  const { eyloSDK } = useEyloSDK();

  return useMemo(() => {
    if (!eyloSDK || !message) return "";
    return eyloSDK.messageService.getMessageContentPlainText(message);
  }, [eyloSDK, message]);
}
