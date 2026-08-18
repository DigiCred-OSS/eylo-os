# Voice runtime

Eylo's voice value is the humane interaction layer around provider audio: turn
state, interruption, silence, call control, transcripts, recordings, and
cleanup. Provider packets alone do not define that experience.

## Two provider paths

The decomposed path uses STT for user audio, an LLM for reasoning/tools, and TTS
for assistant audio. The realtime path delegates audio generation and
understanding to one realtime provider while Eylo retains session, tool, policy,
and artifact ownership.

Browser voice adds WebRTC signalling/media. Telephony adds carrier webhooks and
a bidirectional media stream. All paths converge on canonical conversation,
message, user-session, voice-session, and transcript records.

## Voice config is platform policy

A voice config selects provider configs and defines interruption, silence,
duration, recording, end-call, and interaction settings. The primary Agent's
voice config is fixed when the conversation starts and does not change during a
swarm handoff.

Provider capability projection tells operators which features are native. A
pipeline may implement a platform feature even when the provider does not.

## Turn and interruption handling

Assistant playback completion, not merely model text completion, determines
when the user-silence timer may begin. User speech can interrupt current Agent
audio. The transcript records speech outcome separately from generated text so
model context, operator review, and playback do not claim unheard content was
spoken.

Silence checks such as “Are you still there?” are policy speech, not normal
Agent content. They must not be inserted into canonical model history as if the
Agent independently chose them.

## Call termination

The platform can close an active voice session from silence/max-duration policy,
an end-call phrase, user hangup, transport failure, or the `end_call` system
tool. Telephony-specific carrier cleanup is one adapter effect; browser and
realtime sessions also close through the shared voice-session authority.

## Recording and post-call work

Recording captures the live flow first. Upload, redaction, canonical transcript
processing, and configured policy controls happen asynchronously after the
call. Secondary failure is visible but does not retroactively fail the call.

Storage adapters receive platform-built keys below an operator root/bucket:
organization → owning conversation/call/session → artifact. Callers never
provide a final object path.

## Resource cleanup

Each child session owns its tasks, streams, media tracks, provider clients,
timers, and queues. Normal completion, timeout, cancellation, WebSocket loss,
WebRTC failure, carrier hangup, and abrupt browser closure all converge through
idempotent shutdown. Provider cleanup errors are contained and logged without
leaving the product lifecycle active.
