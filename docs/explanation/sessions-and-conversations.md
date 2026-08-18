# Sessions, conversations, and ownership

A user session and a conversation answer different questions.

- User session: one contact visit or call, including reconnects and technical
  transport facts.
- Conversation: one durable exchange of participants and messages that may
  continue across visits.

## Many-to-many over time

A user may resume the same conversation in a later session. A user may also
switch between several conversations during one session. The
`user_session_conversations` relation records first/last observation of each
pair instead of forcing either entity to own the other.

## Child transport sessions

WebSocket, WebRTC, voice-provider, and telephony sessions are runtime children
of the user session. Each has its own connection/resource lifecycle. They may
fail or reconnect without changing conversation identity.

## Canonical messages

Messages belong to conversations. User, assistant, system, tool-use, tool-result,
and widget/interface content remain visible to organization members in the
operator console. Request status tracks whether the Agent work behind an
assistant response is pending, processing, waiting on tools, or terminal.

Only terminal valid message classes enter future model history. This prevents a
failed, interrupted, or still-processing placeholder from poisoning context or
provider caching.

## Timeline

The session timeline correlates allowlisted durable facts by user-session ID.
It is an operational explanation of what the user experienced, not a total
ordering guarantee or a copy of message content.
