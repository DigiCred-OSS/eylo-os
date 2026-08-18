// WebRTC Connection States - reflects the actual connection lifecycle
export type TVoiceConnectionState =
  | "DISCONNECTED" // No active connection
  | "CONNECTING" // Getting microphone access and setting up connection
  | "NEGOTIATING" // WebRTC offer/answer exchange in progress
  | "ICE_CHECKING" // Finding best connection path (STUN/TURN)
  | "CONNECTED" // WebRTC connected, audio flowing, ready to speak
  | "RECONNECTING" // Connection lost, attempting to reconnect
  | "FAILED" // Connection failed
  | "ERROR"; // Error occurred

export type VoiceRuntimeMode = "browser_decomposed" | "browser_realtime";

export type WebRTCServiceState =
  | "peer_created"
  | "peer_connecting"
  | "peer_connected"
  | "peer_disconnected"
  | "peer_failed"
  | "ice_gathering"
  | "ice_complete"
  | "track_added"
  | "track_removed";

export type VoiceVendorServiceState =
  | "connecting"
  | "connected"
  | "ready"
  | "disconnected"
  | "error";

export type RealtimeServiceState = "inactive" | "ready" | "error";

export interface VoiceLifecyclePayload {
  message?: string;
  timestamp?: number;
  conversation_id?: string;
  [key: string]: unknown;
}

export interface WebRTCLifecyclePayload extends VoiceLifecyclePayload {
  state?: WebRTCServiceState;
}

export interface VoiceVendorLifecyclePayload extends VoiceLifecyclePayload {
  vendor?: string;
  runtime_mode?: VoiceRuntimeMode;
}

export interface VoiceInteractionPayload extends VoiceLifecyclePayload {
  voice_call_id: string;
  call_started_at: number;
  sequence: number;
  state: TVoiceState;
}

export interface VoiceRuntimeError {
  source: "webrtc" | "stt" | "tts" | "realtime";
  message: string;
  code?: string;
}

// Voice Activity States - what the agent is doing
export type TVoiceState =
  | "INACTIVE"
  | "INITIALIZING"
  | "LISTENING"
  | "PROCESSING"
  | "SPEAKING"
  | "ERROR";

export interface VoiceSession {
  id: string;
  conversationId: string;
  state: TVoiceState;
  connectionState: TVoiceConnectionState;
  peerConnection: RTCPeerConnection | null;
  localStream: MediaStream | null;
}

export interface AudioProcessorConfig {
  sampleRate: number;
  channelCount: number;
  enableResampling: boolean;
}
