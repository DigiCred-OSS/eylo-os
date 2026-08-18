import type {
  VoiceVendorLifecyclePayload,
  WebRTCLifecyclePayload,
} from "@eylo/modules/voice/types";
import type { Message } from "@eylo/modules/message/model";

export const EYLO_EVENTS = {
  SYSTEM: "eylo:system",
  ERROR: "eylo:error",
  SDK_INITIALIZED: "eylo:sdk:initialized",
  SDK_SHUTDOWN: "eylo:sdk:shutdown",
  NET_CONNECTING: "eylo:net:connecting",
  NET_CONNECTED: "eylo:net:connected",
  NET_DISCONNECTED: "eylo:net:disconnected",
  WIDGET_INITIALIZED: "eylo:widget:initialized",
  WIDGET_OPEN: "eylo:widget:opened",
  WIDGET_CLOSE: "eylo:widget:closed",
  WIDGET_SHUTDOWN: "eylo:widget:shutdown",
  GLOBAL_STATE_UPDATED: "eylo:state:updated",
  SESSION_INITIALIZED: "eylo:session:initialized",
  SESSION_CLOSED: "eylo:session:closed",
  // contact
  CONTACT_IDENTIFIED: "eylo:contact:identified",
  CONTACT_UPDATED: "eylo:contact:updated",
  CONTACT_CREATED: "eylo:contact:created",
  // conversation
  CONVERSATION_CREATED: "eylo:conversation:created",
  CONVERSATION_UPDATED: "eylo:conversation:updated",
  // messages
  MESSAGE_SENT: "eylo:message:sent",
  MESSAGE_RECEIVED: "eylo:message:received",
  MESSAGE_FEEDBACK: "eylo:message:feedback",
  // Participant
  PARTICIPANT_CREATED: "eylo:participant:created",
  PARTICIPANT_UPDATED: "eylo:participant:updated",
  // TODO: message created should ideally be handled by
  // the message store.conversation store
  // this is a temporary event to test things
  MESSAGE_CREATED: "eylo:message:created",
  MESSAGE_STATUS: "eylo:message:status",
  MESSAGE_TRANSCRIPT: "eylo:message:transcript",
  // webrtc
  WEBRTC_OFFER: "eylo:webrtc:offer",
  WEBRTC_ANSWER: "eylo:webrtc:answer",
  WEBRTC_CANDIDATE: "eylo:webrtc:ice_candidate",
  WEBRTC_HANGUP: "eylo:webrtc:hangup",
  // webrtc state events
  WEBRTC_PEER_CREATED: "eylo:webrtc:peer_created",
  WEBRTC_PEER_CONNECTING: "eylo:webrtc:peer_connecting",
  WEBRTC_PEER_CONNECTED: "eylo:webrtc:peer_connected",
  WEBRTC_PEER_DISCONNECTED: "eylo:webrtc:peer_disconnected",
  WEBRTC_PEER_FAILED: "eylo:webrtc:peer_failed",
  WEBRTC_ICE_GATHERING: "eylo:webrtc:ice_gathering",
  WEBRTC_ICE_COMPLETE: "eylo:webrtc:ice_complete",
  WEBRTC_TRACK_ADDED: "eylo:webrtc:track_added",
  WEBRTC_TRACK_REMOVED: "eylo:webrtc:track_removed",
  // stt state events
  STT_CONNECTING: "eylo:stt:connecting",
  STT_CONNECTED: "eylo:stt:connected",
  STT_READY: "eylo:stt:ready",
  STT_DISCONNECTED: "eylo:stt:disconnected",
  STT_ERROR: "eylo:stt:error",
  // tts state events
  TTS_CONNECTING: "eylo:tts:connecting",
  TTS_CONNECTED: "eylo:tts:connected",
  TTS_READY: "eylo:tts:ready",
  TTS_DISCONNECTED: "eylo:tts:disconnected",
  TTS_ERROR: "eylo:tts:error",
} as const;

export type EventTypes = (typeof EYLO_EVENTS)[keyof typeof EYLO_EVENTS];

export interface EventPayloadMap {
  [EYLO_EVENTS.MESSAGE_CREATED]: Message;
  [EYLO_EVENTS.MESSAGE_FEEDBACK]: Message;
  [EYLO_EVENTS.MESSAGE_TRANSCRIPT]: Message;
  [EYLO_EVENTS.WEBRTC_ANSWER]: { sdp: string; iceServers?: RTCIceServer[] };
  [EYLO_EVENTS.WEBRTC_PEER_CREATED]: WebRTCLifecyclePayload;
  [EYLO_EVENTS.WEBRTC_PEER_CONNECTING]: WebRTCLifecyclePayload;
  [EYLO_EVENTS.WEBRTC_PEER_CONNECTED]: WebRTCLifecyclePayload;
  [EYLO_EVENTS.WEBRTC_PEER_DISCONNECTED]: WebRTCLifecyclePayload;
  [EYLO_EVENTS.WEBRTC_PEER_FAILED]: WebRTCLifecyclePayload;
  [EYLO_EVENTS.WEBRTC_ICE_GATHERING]: WebRTCLifecyclePayload;
  [EYLO_EVENTS.WEBRTC_ICE_COMPLETE]: WebRTCLifecyclePayload;
  [EYLO_EVENTS.WEBRTC_TRACK_ADDED]: WebRTCLifecyclePayload;
  [EYLO_EVENTS.WEBRTC_TRACK_REMOVED]: WebRTCLifecyclePayload;
  [EYLO_EVENTS.STT_CONNECTING]: VoiceVendorLifecyclePayload;
  [EYLO_EVENTS.STT_CONNECTED]: VoiceVendorLifecyclePayload;
  [EYLO_EVENTS.STT_READY]: VoiceVendorLifecyclePayload;
  [EYLO_EVENTS.STT_DISCONNECTED]: VoiceVendorLifecyclePayload;
  [EYLO_EVENTS.STT_ERROR]: VoiceVendorLifecyclePayload;
  [EYLO_EVENTS.TTS_CONNECTING]: VoiceVendorLifecyclePayload;
  [EYLO_EVENTS.TTS_CONNECTED]: VoiceVendorLifecyclePayload;
  [EYLO_EVENTS.TTS_READY]: VoiceVendorLifecyclePayload;
  [EYLO_EVENTS.TTS_DISCONNECTED]: VoiceVendorLifecyclePayload;
  [EYLO_EVENTS.TTS_ERROR]: VoiceVendorLifecyclePayload;
}

export type EventPayloadTuple<E extends EventTypes> = E extends keyof EventPayloadMap
  ? [EventPayloadMap[E]]
  : unknown[];
