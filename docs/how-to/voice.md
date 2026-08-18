# Configure a voice Agent

## Choose one runtime path

Eylo supports two voice paths:

- **Decomposed**: STT → LLM → TTS.
- **Realtime**: one realtime model owns audio input and output.

Both use WebRTC in the browser. Telephony adds a carrier/media-stream boundary.

## Configure the providers

For a decomposed Agent:

1. Create and verify STT, TTS, LLM, and WebRTC configurations.
2. Create a voice config selecting those provider configs.

For a realtime Agent:

1. Create and verify realtime and WebRTC configurations.
2. Create a voice config selecting the realtime path.

For telephony, also configure a carrier. For persisted recordings, configure a
storage provider. Missing required capabilities fail explicitly.

## Set platform voice policy

Configure interruption behavior, silence prompts and termination, maximum
duration, recording, end-call phrases, background sound, and other supported
platform controls. The provider compatibility view shows vendor-native support;
it does not disable platform features the vendor lacks.

## Bind and publish

Bind the voice config to the Agent draft and publish. The primary Agent's voice
config remains fixed for the whole conversation, including swarm handoffs.

## Validate with a human

Check at least:

- microphone permission and first-listen transition;
- user speech reaches STT or the realtime provider;
- assistant audio is continuous and matches its messages;
- barge-in stops the current assistant turn;
- silence prompts wait until assistant playback completes;
- silence termination and maximum duration close the session;
- normal hangup and abrupt browser closure release every stream and task;
- messages appear during the call;
- transcript, session facts, and recording status converge after the call.
