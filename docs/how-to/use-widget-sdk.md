# Use the Widget SDK from Preact

This guide shows how to wrap the headless Widget SDK in Preact. The patterns are
reduced from the working implementation in `widget/preact-ui/`; they are not a
parallel example invented for documentation.

Use the existing Preact widget unless a product needs a different contact
experience. The headless SDK is currently workspace-private, so a custom shell
is maintainer work rather than an npm installation workflow.

## Before you start

You need:

- the API and WebSocket endpoint reachable from the browser;
- one server-issued `WidgetSessionBootstrap`;
- a published Agent allowed by that session;
- browser support for `WebSocket`, `crypto.randomUUID()`, and
  `requestAnimationFrame`;
- `mediaDevices`, `RTCPeerConnection`, `AudioContext`, and secure context when
  voice is enabled.

Read the [Widget SDK reference](../reference/widget-sdk.md) before changing
session, lifecycle, or voice behavior.

## 1. Resolve the session outside the SDK

The SDK accepts a contact session token, not an invitation token. The Preact
implementation resolves the invitation first:

```ts
type WidgetSessionBootstrap = {
  organizationId: string;
  contactId: string;
  initialConversationId?: string;
  sessionToken: string;
  sessionExpiresAt: string;
};

async function exchangeInvitation(
  token: string,
  requestId: string,
): Promise<WidgetSessionBootstrap> {
  const response = await fetch("/api/public/widget-invitations/exchange", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, requestId }),
  });

  if (!response.ok) {
    throw new Error("This chat invitation is unavailable.");
  }

  const value = await response.json();
  return {
    organizationId: value.organizationId,
    contactId: value.contactId,
    initialConversationId: value.conversationId,
    sessionToken: value.sessionToken,
    sessionExpiresAt: value.sessionExpiresAt,
  };
}
```

The production implementation adds three important safeguards:

1. It accepts invitation tokens only between 32 and 512 characters.
2. It hashes the token and keeps the same request ID when retrying the same
   interrupted exchange.
3. It removes the invitation from the visible URL after success or permanent
   rejection.

Reuse `widget/preact-ui/src/invitation-session.ts` rather than replacing those
rules with browser-selected organization/contact IDs.

## 2. Provide one SDK instance

The reference Preact provider subscribes before initialization, waits for both
connection and server user-session state, and suspends rather than terminates
on ordinary unmount.

```tsx
import { Eylo } from "@eylo/sdk";
import { createContext } from "preact";
import type { ComponentChildren } from "preact";
import { useContext, useEffect, useMemo, useState } from "preact/hooks";

type Session = {
  organizationId: string;
  contactId: string;
  sessionToken: string;
};

const SdkContext = createContext<Eylo | null>(null);

export function useEylo(): Eylo {
  const sdk = useContext(SdkContext);
  if (!sdk) throw new Error("useEylo must be used inside EyloProvider");
  return sdk;
}

export function EyloProvider({
  session,
  children,
}: {
  session: Session;
  children: ComponentChildren;
}) {
  const sdk = useMemo(
    () => new Eylo(session.organizationId),
    [session.organizationId],
  );
  const [connected, setConnected] = useState(
    sdk.store.cm.get("isConnected") === true,
  );
  const [hasUserSession, setHasUserSession] = useState(
    Boolean(sdk.store.cm.get("userSessionId")),
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onConnected = () => setConnected(true);
    const onDisconnected = () => setConnected(false);
    sdk.ee.on("eylo:net:connected", onConnected);
    sdk.ee.on("eylo:net:disconnected", onDisconnected);

    const stopConnected = sdk.store.cm.subscribe("isConnected", ({ value }) => {
      setConnected(value === true);
    });
    const stopUserSession = sdk.store.cm.subscribe("userSessionId", ({ value }) => {
      setHasUserSession(Boolean(value));
    });

    void sdk.initialize(session.sessionToken, session.contactId).catch((cause) => {
      setError(cause instanceof Error ? cause.message : "Widget initialization failed");
    });

    return () => {
      stopConnected();
      stopUserSession();
      sdk.ee.off("eylo:net:connected", onConnected);
      sdk.ee.off("eylo:net:disconnected", onDisconnected);
      sdk.suspend();
    };
  }, [sdk, session.contactId, session.sessionToken]);

  if (error) return <div role="alert">{error}</div>;
  if (!connected || !hasUserSession) return <div>Connecting…</div>;

  return <SdkContext.Provider value={sdk}>{children}</SdkContext.Provider>;
}
```

The SDK is a page singleton. Do not use the dependency array above to switch
organizations within the same window. A real organization change must destroy
the widget and load a fresh page.

## 3. Adapt reactive stores to Preact

The Preact implementation uses one generic hook for every scalar store key:

```tsx
import { useEffect, useState } from "preact/hooks";

export function useStoreValue<
  State extends Record<string, unknown>,
  Key extends keyof State,
>(
  store: {
    get(key: Key): State[Key];
    subscribe(
      key: Key,
      callback: (detail: { prev: State[Key]; value: State[Key] }) => void,
    ): () => void;
  },
  key: Key,
) {
  const [value, setValue] = useState(() => store.get(key));

  useEffect(() => {
    const stop = store.subscribe(key, ({ value: next }) => setValue(next));
    setValue(store.get(key));
    return stop;
  }, [store, key]);

  return value;
}
```

Subscribing before the second `get()` closes the gap between initial render and
listener registration. Always return the unsubscribe function from the effect.

Repository stores use the same pattern around their list key:

```tsx
function useConversations() {
  const sdk = useEylo();
  const store = sdk.store.conversationStore;
  const [items, setItems] = useState(() => store.list_());

  useEffect(() => {
    const refresh = () => setItems([...store.list_()]);
    const stop = store.subscribe("conversations", refresh);
    refresh();
    return stop;
  }, [store]);

  return items;
}
```

## 4. Load the conversation list

`listConversations()` hydrates the SDK stores and resolves with the returned
row count. The reference UI uses that count to decide whether another page may
exist:

```tsx
const PAGE_SIZE = 5;

async function loadConversationPage(sdk: Eylo, page: number) {
  const count = await sdk.conversationService.listConversations({
    page,
    limit: PAGE_SIZE,
  });

  return {
    conversations: sdk.store.conversationStore.list_(),
    hasMore: count === PAGE_SIZE,
  };
}
```

Render unread count and last activity from the hydrated conversation. Call
`markRead(conversationId)` after the selected conversation and its current
messages are visible.

## 5. Start a conversation with request correlation

Conversation creation is asynchronous. The Preact implementation stores the
pending request ID, matches it against `eylo:conversation:created`, then sends
the first text message through the normal message path.

```tsx
import { useEffect, useRef } from "preact/hooks";

function useStartConversation(
  agentId: string,
  contactId: string,
  onError: (message: string) => void,
) {
  const sdk = useEylo();
  const pending = useRef<{
    requestId: string;
    firstMessage: string;
  } | null>(null);

  useEffect(() => {
    const onCreated = (...args: unknown[]) => {
      const conversation = args[0] as { id: string };
      const requestId = args[1] as string | undefined;
      if (!pending.current || pending.current.requestId !== requestId) return;

      const firstMessage = pending.current.firstMessage;
      pending.current = null;
      const sent = sdk.sendMessage(
        { conversationId: conversation.id, text: firstMessage },
        crypto.randomUUID(),
      );
      if (!sent) {
        onError("Conversation created, but message transport is offline");
      }
    };

    sdk.ee.on("eylo:conversation:created", onCreated);
    return () => sdk.ee.off("eylo:conversation:created", onCreated);
  }, [onError, sdk]);

  return (firstMessage: string) => {
    const requestId = crypto.randomUUID();
    pending.current = { requestId, firstMessage };
    sdk.startConversation(
      {
        from: { kind: "CONTACT", id: contactId },
        to: { kind: "AGENT", id: agentId },
        message: { content: [] },
        context: {},
      },
      requestId,
    );
  };
}
```

Do not send the first text both inside the create payload and again as a normal
message. The current Preact flow creates the conversation, then sends exactly
one durable message.

For a voice-first conversation, keep the same correlation pattern and call
`startVoiceSession(conversation.id)` instead of sending the first text.

## 6. Load and stream messages

Load a correlated history page, then merge live messages by ID. Subscribe to
created, feedback, and transcript events before starting the load so a live
event cannot be lost between request and response.

```tsx
useEffect(() => {
  let disposed = false;

  const onMessage = (...args: unknown[]) => {
    const model = args[0] as Parameters<typeof sdk.messageService.resolveMessage>[0];
    if (model.conversationId !== conversationId) return;
    const message = sdk.messageService.resolveMessage(model);
    setMessages((current) => mergeById(current, [message]));
  };

  sdk.ee.on("eylo:message:created", onMessage);
  sdk.ee.on("eylo:message:feedback", onMessage);
  sdk.ee.on("eylo:message:transcript", onMessage);

  void sdk.conversationService
    .loadMoreMessages(conversationId, 10, 0)
    .then((page) => {
      if (!disposed) setMessages((current) => mergeById(current, page.messages));
    });

  return () => {
    disposed = true;
    sdk.ee.off("eylo:message:created", onMessage);
    sdk.ee.off("eylo:message:feedback", onMessage);
    sdk.ee.off("eylo:message:transcript", onMessage);
  };
}, [sdk, conversationId]);
```

The production `mergeConversationMessages()` also removes a transient voice
transcript when a committed row with the same `externalId` arrives, then sorts
by `createdAt`. Preserve that rule in another renderer.

Participant, contact, and Agent records may hydrate after the message. The
reference UI subscribes to all three relation stores and re-runs
`resolveMessage_byId()` when any changes.

The omitted `mergeById()` helper must preserve the row with each stable message
ID, replace a transient row when a committed row has the same `externalId`, and
sort the result by `createdAt` ascending. The reference implementation is
`mergeConversationMessages()` in `widget/preact-ui/src/hooks/useEyloStore.ts`.

## 7. Show Agent progress

Agent progress is separate from committed messages:

```tsx
useEffect(() => {
  return sdk.agentService.onStatusChange((status) => {
    if (status.conversationId !== conversationId) return;
    if (status.requestId !== activeRequestId.current) return;

    setProgress(status);
    if (status.terminal) activeRequestId.current = null;
  });
}, [sdk, conversationId]);
```

Use `runStartedAt` and monotonically increasing `sequence` to reject stale
updates when reconnects or concurrent turns reorder delivery. Do not hide the
message input permanently on a missing non-terminal event; terminal success or
failure is authoritative.

## 8. Enable conversation-file upload

The Preact UI checks capability per conversation, hides the upload action when
denied, uploads without asking the user for a destination, then polls the
ingestion receipt:

```ts
const capability = await sdk.knowledgeService.getUploadCapability(conversationId);
if (!capability.allowed) return;

let ingestion = await sdk.knowledgeService.uploadFile(conversationId, file);
const terminal = new Set(["succeeded", "failed", "cancelled"]);

while (!terminal.has(ingestion.state)) {
  await new Promise((resolve) => setTimeout(resolve, 1_000));
  ingestion = await sdk.knowledgeService.getIngestion(
    conversationId,
    ingestion.jobId,
  );
}

if (ingestion.state !== "succeeded") {
  throw new Error(ingestion.lastError ?? "The file could not be indexed");
}
```

In a component, replace the open loop with a cancellable timer as
`ConversationDetails` does. Stop polling on unmount or conversation change.

## 9. Render end-user connection requirements

An Agent tool may signal that the current contact must connect a vendor. The
Preact connection panel subscribes to the manager, renders every pending
requirement, and dispatches by auth kind:

```tsx
const manager = sdk.store.connectionStateManager;

useEffect(() => {
  const refresh = () => setRequirements(manager.getPendingAuths());
  const stop = manager.subscribe(refresh);
  refresh();
  return stop;
}, [manager]);

async function connect(requirement: {
  id: string;
  auth_kind: "oauth2" | "api_key" | "basic" | "no_auth" | null;
}) {
  if (requirement.auth_kind === "oauth2") {
    await manager.openOAuthPopup(requirement.id);
    return;
  }

  if (requirement.auth_kind === "api_key") {
    await manager.connectWithCredentials(requirement.id, { apiKey });
    return;
  }

  if (requirement.auth_kind === "basic") {
    await manager.connectWithCredentials(requirement.id, { username, password });
  }
}
```

Call popup methods directly from a user gesture where possible. Show failed
requirements with retry and dismiss actions. Never put credentials in
conversation messages or host logs.

## 10. Add voice controls

Project voice state directly from `voiceStore`:

```tsx
const active = useStoreValue(sdk.store.voiceStore, "isSessionActive");
const connection = useStoreValue(sdk.store.voiceStore, "connectionState");
const interaction = useStoreValue(sdk.store.voiceStore, "interactionState");
const remoteStream = useStoreValue(sdk.store.voiceStore, "remoteStream");
const error = useStoreValue(sdk.store.voiceStore, "lastError");
```

Start only from a user action so microphone permission has browser gesture
context:

```ts
await sdk.startVoiceSession(conversationId);
```

Attach `remoteStream` to an audio element and clean it up when the stream
changes. The reference widget also stops voice whenever the conversation view
unmounts:

```tsx
useEffect(() => {
  return () => {
    if (sdk.voiceService.hasActiveSession()) {
      void sdk.voiceService.endVoiceCall("Conversation view closed");
    }
  };
}, [sdk]);
```

Drive listening/processing/speaking UI from `interactionState`, not from media
permission or WebRTC connection alone.

## 11. Render interactive Agent UI

Register the component catalog once before rendering messages:

```ts
import { registerDefaultWidgetComponents } from "@eylo";

registerDefaultWidgetComponents();
```

For a `WIDGET` message:

```ts
const result = sdk.messageService.getWidgetPayload(message);
if (!result.ok) {
  renderInvalidPayload(result.issues);
} else {
  renderRegisteredComponent(result.value, (interaction) => {
    sdk.sendWidgetResponse(
      {
        conversationId: message.conversationId,
        widgetMessageId: message.id,
        component: interaction.component,
        action: interaction.action,
        data: interaction.data,
      },
      crypto.randomUUID(),
    );
  });
}
```

The SDK validates payloads and responses. Your UI must still map component
names to safe Preact renderers and add a render error boundary. See
`widget/preact-ui/src/components/DynamicWidget/` for the single/compound
renderer split.

## 12. Tear down at the correct level

Use two cleanup levels:

```ts
// Recoverable component unmount or host remount.
sdk.suspend();

// Explicit end-user widget destruction.
await sdk.voiceService.endVoiceCall("Widget destroyed");
sdk.terminate();
```

Before either call:

- remove event listeners with the same callback reference;
- run every store/Agent/auth unsubscribe function;
- cancel Knowledge polling timers;
- stop the active voice session and release media;
- clear host-only optimistic state.

The Preact bundle's `window.EyloWidget.destroy()` terminates the session,
unmounts the root, removes `#eylo-widget`, and clears `window.Eylo`.

## Verification checklist

- Invalid or expired invitation shows a generic unavailable state.
- UI does not render until transport and `userSessionId` are ready.
- Refresh/reconnect continues the same user session without duplicating it
  across copied tabs.
- Conversation creation matches the exact request ID.
- Messages appear live and committed messages replace transient transcripts.
- Pagination does not duplicate messages.
- Agent terminal success and failure both re-enable input.
- Upload is absent when capability is false; successful ingestion becomes
  queryable in that conversation.
- OAuth rejects the wrong callback origin and reports popup blocking.
- Voice state follows connection and interaction state independently.
- Leaving voice stops microphone tracks and closes the peer connection.
- Every listener, store subscription, timer, and popup watcher is cleaned up.

## Reference implementation map

| Pattern | Preact source |
| --- | --- |
| Session exchange and retry identity | `widget/preact-ui/src/invitation-session.ts` |
| Provider, readiness gate, suspend/terminate | `widget/preact-ui/src/main.tsx` |
| Store and event hooks | `widget/preact-ui/src/hooks/useEyloStore.ts` |
| Command hooks | `widget/preact-ui/src/hooks/useActions.ts` |
| Request-correlated creation | `widget/preact-ui/src/components/ConversationCreate/` |
| Messages, uploads, and voice cleanup | `widget/preact-ui/src/components/ConversationDetails/` |
| End-user integration auth | `widget/preact-ui/src/components/ConnectionPanel/` |
| Interactive component registry | `widget/preact-ui/src/design-system/compositions/register.ts` |
| Interactive rendering | `widget/preact-ui/src/components/DynamicWidget/` |
