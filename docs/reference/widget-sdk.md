# Widget SDK

The Widget SDK is the browser-side runtime for an Eylo contact. It owns the
authenticated WebSocket connection, reactive client state, conversation and
message commands, conversation-file upload, end-user integration
authorization, interactive-widget validation, and browser voice/WebRTC
lifecycle.

The current source contract lives under `widget/src/`. The working Preact UI
under `widget/preact-ui/` is the reference consumer of that contract.

## Distribution status

There are two distinct surfaces:

| Surface | Current status | Intended consumer |
| --- | --- | --- |
| Preact widget bundle | Built as `eylo-widget.js` and served by Eylo or Vite | End users who need the complete chat and voice UI |
| Headless TypeScript SDK | Source API consumed inside this workspace | Maintainers building another UI shell |

`widget/package.json` is private and versioned `0.0.0`. There is no published
`eylo-sdk` npm package yet. Do not document or depend on an `npm install`
workflow until packaging, semantic versioning, generated declarations, and a
public import path exist.

The canonical source barrel is `widget/src/index.ts`. The Preact UI also uses
workspace-internal imports such as `@eylo/sdk`, `@eylo/events`, and
`@eylo/modules/conversation`; those aliases are not external package names.

## Runtime ownership

| Concern | Owner |
| --- | --- |
| Issue a production chat invitation | Trusted host or organization member API |
| Exchange an invitation for a contact session | Host/Preact bootstrap layer |
| Choose organization, contact, Agent, and optional conversation authority | Server-issued invitation/session |
| Maintain WebSocket transport and reconnect state | SDK |
| Hydrate browser-side entities | SDK services and stores |
| Render screens and controls | Preact UI or another host UI |
| Persist conversations, messages, runs, files, and connections | Server |
| Resolve provider and Agent configuration | Server |

Passing an `organizationId` to `new Eylo(...)` selects the WebSocket URL. It
does not grant access to that organization. The session token remains the
authority and must match the organization and contact resolved by the server.

## Session bootstrap contract

The SDK starts from a server-issued contact session:

```ts
type WidgetSessionBootstrap = {
  organizationId: string;
  contactId: string;
  initialConversationId?: string;
  sessionToken: string;
  sessionExpiresAt: string;
};
```

Production Preact flow:

1. A trusted caller issues an invitation for one contact and one published
   Agent revision.
2. The widget receives the opaque invitation token in the `invitation` query
   parameter.
3. `POST /api/public/widget-invitations/exchange` consumes the token with a
   stable request ID.
4. The response supplies the organization, contact, conversation, session
   token, and expiry.
5. The invitation is removed from the visible URL and the bootstrap is kept in
   `sessionStorage` until expiry.
6. The SDK opens the WebSocket with that session token.

The exchange belongs outside `Eylo.initialize()`. The SDK never accepts an
invitation token and never derives identity from untrusted page input.

`POST /api/public/widget-development/session` is a local-only convenience. It
exists only when the server has a paired development organization and contact
configured. It is not a production identity fallback.

## `Eylo` lifecycle

```ts
import { Eylo } from "@eylo/sdk";

const sdk = new Eylo(session.organizationId);
await sdk.initialize(session.sessionToken, session.contactId);
```

`Eylo` is a singleton in the current implementation. The first construction in
a page owns the organization and all singleton services/stores. Do not create
multiple organization-scoped SDKs in one window. Changing organizations
requires destroying the current widget and loading a fresh page.

| Member | Contract |
| --- | --- |
| `new Eylo(organizationId)` | Construct or return the page-level singleton |
| `initialize(sessionToken, contactId?)` | Set contact scope and begin transport initialization |
| `suspend()` | Disconnect the transport but preserve the browser user-session ID for remount/reconnect |
| `terminate()` | Disconnect and end the browser user session |

`await sdk.initialize(...)` means initialization was requested successfully.
It does not mean the WebSocket and server-side user session are ready. A UI is
ready only when both are true:

```ts
const connected = sdk.store.cm.get("isConnected") === true;
const hasUserSession = Boolean(sdk.store.cm.get("userSessionId"));
```

The Preact UI subscribes to both values before calling `initialize()` so it
cannot miss an early transition.

Use `suspend()` for component unmount, route replacement, or recoverable host
UI teardown. Use `terminate()` only when the end user intentionally closes the
widget session. `terminate()` clears reconnect continuity.

## Top-level properties and convenience methods

| Member | Result |
| --- | --- |
| `ee` | SDK event emitter |
| `store` | Root reactive store |
| `contactService` | Contact hydration and lookup |
| `conversationService` | Conversation list, creation, lookup, and message history |
| `messageService` | Message send, feedback, widget response, and projection helpers |
| `participantService` | Participant resolution |
| `agentService` | Available Agents, lifecycle status, and tool/integration summaries |
| `knowledgeService` | Conversation-file capability, upload, and ingestion status |
| `voiceService` | Browser media and WebRTC voice lifecycle |

The convenience commands delegate to the corresponding service:

```ts
sdk.startConversation(request, requestId);
sdk.sendMessage(request, requestId);
sdk.sendWidgetResponse(request, requestId);
sdk.sendFeedback(conversationId, messageRequestId, feedback);
await sdk.startVoiceSession(conversationId);
await sdk.stopVoiceSession();
```

`sendMessage()`, `sendWidgetResponse()`, and `sendFeedback()` return a boolean.
`true` means the connected WebSocket accepted the outgoing frame. It does not
mean the server committed the message or the Agent completed its work. Observe
the corresponding server projection and Agent lifecycle status.

Use `crypto.randomUUID()` for every command request ID. Keep the ID until its
correlated event arrives; do not match concurrent work only by conversation.

## Conversation service

| Method | Contract |
| --- | --- |
| `startConversation(data, requestId)` | Request a WIDGET conversation; result arrives on `eylo:conversation:created` with the same request ID |
| `listConversations({ page?, limit? })` | Fetch one aggregate page, hydrate related stores, and resolve with the number of returned conversations |
| `markRead(conversationId)` | Mark the conversation read; returns whether the frame was accepted |
| `resolveConversation(conversationId, messageLimit?)` | Return hydrated context, or request it and return `undefined` while data arrives |
| `getLastMessage(conversationId)` | Return the latest hydrated message |
| `loadMoreMessages(conversationId, limit?, offset?)` | Resolve a correlated message page and hydrate the stores |

Conversation creation shape:

```ts
type ConversationCreate = {
  from: {
    kind: "CONTACT" | "AGENT";
    id?: string;
    externalId?: string;
  };
  to: {
    kind: "CONTACT" | "AGENT";
    id?: string;
    externalId?: string;
  };
  message: {
    content: Array<{ kind: "TEXT"; value: string }>;
  };
  context?: Record<string, unknown>;
  externalId?: string;
  channel?: "PHONE" | "CHAT" | "WEB" | "WIDGET" | "SMS" | "API";
};
```

The service always sends new SDK conversations as `WIDGET`; callers cannot use
the `channel` field to impersonate another transport.

`listConversations()` returns a count, not the rows. Read the hydrated rows
from `sdk.store.conversationStore.list_()` and subscribe to the
`conversations` key. `loadMoreMessages()` returns rows directly because the
caller needs exact page boundaries.

## Message service

| Method | Contract |
| --- | --- |
| `sendMessage({ conversationId, text, context? }, requestId)` | Send a user text message |
| `sendWidgetResponse(data, requestId)` | Submit one structured interaction against a widget message |
| `sendFeedback(conversationId, messageRequestId, feedback)` | Send `positive` or `negative` feedback for the matching message request |
| `resolveMessage_byId(messageId)` | Return a hydrated message or request missing data and return `undefined` |
| `resolveMessage(messageModel)` | Add participant/contact projections to a message model |
| `resolve_byConversationId(conversationId)` | Return hydrated messages sorted oldest first |
| `getMessageContent(message)` | Produce display text or allowed HTML-backed content |
| `getMessageContentPlainText(message)` | Produce plain text for previews and accessible summaries |
| `getWidgetPayload(message)` | Validate and return a single or compound interactive payload |
| `getWidgetResponseData(message)` | Decode a submitted widget response |

Message projections include `USER`, `ASSISTANT`, `SYSTEM`, `TOOL_USE`, and
`TOOL_RESULT`, plus `WIDGET` and `WIDGET_RESPONSE` content. A contact-facing UI
may intentionally show only user and assistant messages, while an operator UI
can show every kind.

Live voice transcript messages have `meta.transient === true`. A later
committed message with the same `externalId` replaces the transient row. Treat
the committed row as canonical.

## Agent and participant services

### Agent

| Method | Contract |
| --- | --- |
| `listAgents()` | Return Agents already announced by the server for this widget session |
| `resolveAgent_byID(agentId)` | Return one hydrated Agent |
| `onStatusChange(callback)` | Subscribe to correlated Agent-run progress; returns an unsubscribe function |
| `fetchAgentIntegrations(agentId)` | Fetch the Agent's granted curated tools grouped by integration |
| `fetchBulkAgentIntegrations(agentIds)` | Resolve integration groups for several Agents without an N+1 request pattern |

Agent status values are `thinking`, `processing`, `tool_executing`,
`tool_completed`, `complete`, or `error`. Every accepted lifecycle update
contains `conversationId`, `requestId`, `runId`, `runStartedAt`, `sequence`, and
`terminal`; terminal updates may include `outcome`.

### Contact and participant

| Method | Contract |
| --- | --- |
| `contactService.identify(data)` | Send contact identification data; production identity still remains constrained by the session |
| `contactService.resolveContact_byID(id)` | Return or request a contact |
| `contactService.resolveContact_byExternalID(externalId)` | Return or request a contact by external ID |
| `participantService.resolveParticipant_byID(id)` | Resolve a participant to the hydrated Agent or contact |

The SDK currently resolves contact and Agent participants. `MEMBER` is a valid
domain participant kind but is not resolved by the contact-facing SDK.

## Conversation Knowledge files

Conversation uploads are normal conversation-scoped Knowledge. The end user
does not choose a destination.

| Method | Contract |
| --- | --- |
| `getUploadCapability(conversationId)` | Return `{ allowed: boolean }` for the current session, conversation, and Agent |
| `uploadFile(conversationId, file)` | Upload a file and return an ingestion receipt |
| `getIngestion(conversationId, jobId)` | Read the current ingestion state |

Every call derives `organizationId`, `sessionId`, and `userSessionId` from the
active SDK store. A missing active session is an error. The returned ingestion
receipt contains `jobId`, `documentId`, `state`, `title`, `sourceUri`, and
`lastError`.

The current Preact UI treats `succeeded`, `failed`, and `cancelled` as terminal
states and polls non-terminal jobs once per second. Show file upload only when
`allowed` is true.

## End-user integration connections

`sdk.store.connectionStateManager` receives `auth:required` signals produced
when an Agent needs a contact-owned integration connection.

| Method | Contract |
| --- | --- |
| `subscribe(callback)` | Observe requirement changes; returns an unsubscribe function |
| `getPendingAuths()` | Return pending, connecting, or failed requirements |
| `openOAuthPopup(requirementId)` | Run the server-origin-pinned OAuth popup flow |
| `connectWithCredentials(requirementId, credentials)` | Submit API-key or basic credentials for the current contact |
| `retryAuth(requirementId)` | Move a failed requirement back to pending |
| `dismissAuth(requirementId)` | Dismiss one requirement |

An auth requirement identifies the integration, vendor, auth kind,
conversation, contact, status, message, and optional error. OAuth, API key, and
basic auth are supported by the manager. Credentials and ownership are sent to
session-authenticated widget endpoints; the browser does not select a different
contact owner.

Only one OAuth popup may be active at a time. Popup-blocked errors must be shown
to the user, and the callback is accepted only from the server-provided origin.

## Voice service and state

`startVoiceSession(conversationId)` checks browser media capabilities, asks for
microphone permission, binds the server-selected voice/provider config,
prepares WebRTC, and negotiates audio. Voice cannot start before the SDK is
connected and the conversation exists.

| Method | Contract |
| --- | --- |
| `startVoiceSession(conversationId)` | Start or await the single in-progress browser voice session |
| `endVoiceCall(reason?, { notifyServer? }?)` | Stop tracks, close audio and peer resources, optionally signal hangup, and reset state |
| `hasActiveSession()` | Return the current active-session flag |
| `getConnectionState()` | Return the connection state machine's current state |
| `getStateHistory()` | Return a diagnostic transition log |

Connection states:

`DISCONNECTED`, `CONNECTING`, `NEGOTIATING`, `ICE_CHECKING`, `CONNECTED`,
`RECONNECTING`, `FAILED`, `ERROR`.

Interaction states:

`INACTIVE`, `INITIALIZING`, `LISTENING`, `PROCESSING`, `SPEAKING`, `ERROR`.

Subscribe to these `voiceStore` keys for UI state:

| Key | Meaning |
| --- | --- |
| `isSessionActive` | A voice start or active voice session exists |
| `connectionState` | Browser/WebRTC connection lifecycle |
| `interactionState` | Listening, processing, or speaking turn state |
| `runtimeMode` | `browser_decomposed` or `browser_realtime` |
| `webrtcState` | Detailed peer/ICE/track lifecycle |
| `sttState`, `ttsState`, `realtimeState` | Provider readiness |
| `sttVendor`, `ttsVendor` | Active decomposed provider identifiers |
| `remoteStream`, `localStream` | Browser media streams |
| `statusMessage`, `lastError` | User-facing status and structured failure |

Always call `endVoiceCall()` when leaving the active conversation. The method
is idempotent across duplicate cleanup requests and releases local/remote
tracks, WebRTC senders, the peer connection, pending negotiations, and audio
processing resources.

## Reactive stores

Every SDK store supports:

```ts
const value = store.get("someKey");
const stop = store.subscribe("someKey", ({ prev, value }) => {
  // Project the state into the host framework.
});

stop();
```

It also exposes `getSnapshot()` and `subscribeToStateChange()`. Entity stores
add `list_()`, `get_(id)`, and `get_byExternalId(externalId)`. The underscore
methods are the current repository API used by the Preact UI, but they are not
yet a separately versioned external contract.

Repository list keys:

| Store | List key |
| --- | --- |
| `contactStore` | `contacts` |
| `conversationStore` | `conversations` |
| `conversationStore.messageStore` | `messages` |
| `participantStore` | `participants` |
| `agentStore` | `agents` |

Subscriptions are batched through `requestAnimationFrame`. Always read the
current value immediately after subscribing, then unsubscribe during component
cleanup.

## Events

Register and remove the same function reference:

```ts
const onConnected = () => setConnected(true);

sdk.ee.on("eylo:net:connected", onConnected);
sdk.ee.off("eylo:net:connected", onConnected);
```

The current root barrel exports the `EventTypes` type but not the
`EYLO_EVENTS` value. Workspace code may import `EYLO_EVENTS` from the internal
`@eylo/events` alias; portable examples use the literal event strings.

Events emitted by the current SDK:

| Category | Events |
| --- | --- |
| Transport | `eylo:net:connecting`, `eylo:net:connected`, `eylo:net:disconnected`, `eylo:error` |
| Contact | `eylo:contact:identified`, `eylo:contact:updated`, `eylo:contact:created` |
| Conversation | `eylo:conversation:created`, `eylo:conversation:updated` |
| Message | `eylo:message:created`, `eylo:message:feedback`, `eylo:message:transcript` |
| Participant | `eylo:participant:created` |
| WebRTC | `eylo:webrtc:answer`, `eylo:webrtc:hangup`, plus peer/ICE/track lifecycle events |
| STT | `eylo:stt:connecting`, `connected`, `ready`, `disconnected`, `error` |
| TTS | `eylo:tts:connecting`, `connected`, `ready`, `disconnected`, `error` |

The event catalog also reserves names for SDK, widget, session, message-status,
and outbound signaling stages. A declared constant is not proof that the
current SDK emits it. Build UI behavior from the emitted-event table or a
reactive store, not from a reserved name.

`eylo:conversation:created` emits the created conversation followed by the
request ID. Message events emit the SDK message model. Convert it with
`messageService.resolveMessage()` when participant/contact projections are
needed.

## Interactive widget payloads

The root barrel exposes a registry and validators for Agent-produced UI:

- `registerWidgetComponent()` and `registerWidgetComponents()`;
- `registerDefaultWidgetComponents()`;
- `getRegisteredWidgetComponent()` and list/schema helpers;
- `validateWidgetPayload()` and `validateCompoundWidgetPayload()`;
- `isCompoundWidgetPayload()`;
- `clearWidgetComponentRegistry()`.

Register component definitions before processing widget messages. The Preact
UI calls `registerDefaultWidgetComponents()` once at startup, validates each
`WIDGET` message through `messageService.getWidgetPayload()`, maps registered
component names to Preact renderers, and sends interactions with
`sendWidgetResponse()`.

Validation covers active component status, schema types and constraints,
compound-tree identity, cycles, orphans, allowed layout parents, tree depth,
and component count. Registration validates data; rendering remains the host
UI's responsibility.

## Preact bundle globals

The built Preact UI currently creates these browser globals:

| Global | Contract |
| --- | --- |
| `window.Eylo` | Current SDK instance or `null` |
| `window.EyloWidget.initialize(props)` | Mount the Preact provider into `#eylo-widget`, creating the element if needed |
| `window.EyloWidget.destroy()` | Terminate the SDK, unmount Preact, and remove the root element |
| `window.EyloWidget.widget` | The Preact provider component |

Initialization props are the session bootstrap identity plus optional
`initialConversationId` and theme configuration. The standalone bundle calls
the invitation/development bootstrap automatically. These globals are a
current UI implementation contract, not a published, semantically versioned
browser SDK.

## Failure and reconnect rules

- Empty session tokens fail before the connection opens.
- `send*` returning `false` means the WebSocket is unavailable; retain or
  restore user input and show a connection error.
- Conversation list/history promises time out after 10 seconds.
- Missing entity resolvers may start hydration and return `undefined`; render a
  loading state and subscribe instead of treating it as a permanent 404.
- Knowledge HTTP calls require active session and user-session IDs.
- Voice failures expose `lastError` and reject the start promise after cleanup.
- Disconnect resets pending integration auth state.
- `suspend()` preserves user-session continuity; `terminate()` clears it.

## Source map

| Contract | Source |
| --- | --- |
| SDK facade | `widget/src/sdk/Eylo.ts` |
| Public source barrel | `widget/src/index.ts` |
| Events | `widget/src/events/` |
| Reactive stores | `widget/src/base/`, `widget/src/store/`, module stores |
| Transport/session state | `widget/src/net/` |
| Conversation, message, Agent, Knowledge, voice services | `widget/src/modules/` |
| Production/local session bootstrap | `widget/preact-ui/src/invitation-session.ts` |
| Reference Preact provider | `widget/preact-ui/src/main.tsx` |
| Reference hooks and commands | `widget/preact-ui/src/hooks/` |
| Conversation files | `widget/preact-ui/src/components/ConversationDetails/` |
| End-user connection prompts | `widget/preact-ui/src/components/ConnectionPanel/` |
| Dynamic widget rendering | `widget/preact-ui/src/components/DynamicWidget/` |

Use [Use the Widget SDK from Preact](../how-to/use-widget-sdk.md) for an
implementation-oriented path based on those sources.
