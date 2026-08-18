// hooks/useVoiceSystemState.ts
import type { Eylo } from "@eylo/sdk/Eylo";
import type {
  TVoiceConnectionState,
  TVoiceState,
  VoiceRuntimeError,
  VoiceVendorServiceState,
  WebRTCServiceState,
} from "@eylo/modules/voice/types";
import { useEffect, useMemo, useState } from "preact/hooks";
import { logger } from "../utils";

export type VoiceSystemState = {
  connectionState: TVoiceConnectionState;
  webrtc: WebRTCServiceState | null;
  stt: VoiceVendorServiceState | null;
  tts: VoiceVendorServiceState | null;
  realtime: "inactive" | "ready" | "error";
  sttVendor: string | null;
  ttsVendor: string | null;
  statusMessage: string | null;
  lastError: VoiceRuntimeError | null;
  interaction: TVoiceState;
};

export type VoiceUiState =
  | "initializing"
  | "listening"
  | "processing"
  | "speaking"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "error";

interface UseVoiceSystemStateOptions {
  eyloSDK: Eylo | undefined;
  isVoiceActive: boolean;
}

interface UseVoiceSystemStateReturn {
  voiceSystemState: VoiceSystemState;
  canUserSpeak: boolean;
  voiceState: VoiceUiState;
}

const INITIAL_VOICE_SYSTEM_STATE: VoiceSystemState = {
  connectionState: "DISCONNECTED",
  webrtc: null,
  stt: null,
  tts: null,
  realtime: "inactive",
  sttVendor: null,
  ttsVendor: null,
  statusMessage: null,
  lastError: null,
  interaction: "INACTIVE",
};

function getVoiceSystemSnapshot(eyloSDK: Eylo | undefined): VoiceSystemState {
  const voiceStore = eyloSDK?.store.voiceStore;
  if (!voiceStore) return INITIAL_VOICE_SYSTEM_STATE;

  return {
    connectionState: voiceStore.get("connectionState"),
    webrtc: voiceStore.get("webrtcState"),
    stt: voiceStore.get("sttState"),
    tts: voiceStore.get("ttsState"),
    realtime: voiceStore.get("realtimeState"),
    sttVendor: voiceStore.get("sttVendor"),
    ttsVendor: voiceStore.get("ttsVendor"),
    statusMessage: voiceStore.get("statusMessage"),
    lastError: voiceStore.get("lastError"),
    interaction: voiceStore.get("interactionState"),
  };
}

/**
 * Custom hook to manage voice system state transitions
 *
 * Tracks WebRTC, STT (Speech-to-Text), and TTS (Text-to-Speech) states
 * and determines when the user can speak.
 *
 * User can speak when:
 * - WebRTC peer is connected
 * - STT is ready
 */
export function useVoiceSystemState({
  eyloSDK,
  isVoiceActive,
}: UseVoiceSystemStateOptions): UseVoiceSystemStateReturn {
  const [voiceSystemState, setVoiceSystemState] = useState<VoiceSystemState>(() =>
    getVoiceSystemSnapshot(eyloSDK)
  );
  const [voiceState, setVoiceState] = useState<VoiceUiState>("initializing");

  const canUserSpeak = useMemo(() => {
    const webrtcReady = voiceSystemState.webrtc === "peer_connected";
    const sttReady = voiceSystemState.stt === "ready";
    return webrtcReady && sttReady;
  }, [voiceSystemState]);

  useEffect(() => {
    const voiceStore = eyloSDK?.store.voiceStore;
    if (!voiceStore || !isVoiceActive) {
      setVoiceSystemState(INITIAL_VOICE_SYSTEM_STATE);
      return;
    }

    setVoiceSystemState(getVoiceSystemSnapshot(eyloSDK));

    const refresh = () => setVoiceSystemState(getVoiceSystemSnapshot(eyloSDK));
    const unsubscribers = [
      voiceStore.subscribe("connectionState", refresh),
      voiceStore.subscribe("webrtcState", refresh),
      voiceStore.subscribe("sttState", refresh),
      voiceStore.subscribe("ttsState", refresh),
      voiceStore.subscribe("realtimeState", refresh),
      voiceStore.subscribe("sttVendor", refresh),
      voiceStore.subscribe("ttsVendor", refresh),
      voiceStore.subscribe("statusMessage", refresh),
      voiceStore.subscribe("lastError", refresh),
      voiceStore.subscribe("interactionState", refresh),
    ];

    return () => {
      unsubscribers.forEach((unsubscribe) => unsubscribe());
    };
  }, [eyloSDK, isVoiceActive]);

  useEffect(() => {
    if (!isVoiceActive) {
      setVoiceState("initializing");
      return;
    }

    if (
      voiceSystemState.connectionState === "ERROR" ||
      voiceSystemState.connectionState === "FAILED" ||
      voiceSystemState.stt === "error" ||
      voiceSystemState.tts === "error" ||
      voiceSystemState.webrtc === "peer_failed" ||
      voiceSystemState.realtime === "error" ||
      voiceSystemState.interaction === "ERROR"
    ) {
      setVoiceState("error");
      logger.error("[Voice] Connection failed", voiceSystemState.lastError);
      return;
    }

    if (voiceSystemState.connectionState === "RECONNECTING") {
      setVoiceState("reconnecting");
      logger.warn("[Voice] Reconnecting");
      return;
    }

    if (
      voiceSystemState.connectionState === "DISCONNECTED" ||
      voiceSystemState.stt === "disconnected" ||
      voiceSystemState.tts === "disconnected" ||
      voiceSystemState.webrtc === "peer_disconnected"
    ) {
      setVoiceState("disconnected");
      logger.warn("[Voice] Connection lost");
      return;
    }

    if (voiceSystemState.interaction === "SPEAKING") {
      setVoiceState("speaking");
      return;
    }

    if (voiceSystemState.interaction === "PROCESSING") {
      setVoiceState("processing");
      return;
    }

    if (voiceSystemState.interaction === "LISTENING" && canUserSpeak) {
      setVoiceState("listening");
      return;
    }

    if (canUserSpeak && voiceSystemState.tts === "ready") {
      setVoiceState("connected");
      logger.debug("[Voice] ✓ Ready for conversation - WebRTC, STT, and TTS ready");
      return;
    }

    if (canUserSpeak) {
      setVoiceState("listening");
      return;
    }

    if (
      voiceSystemState.connectionState === "CONNECTING" ||
      voiceSystemState.connectionState === "NEGOTIATING" ||
      voiceSystemState.connectionState === "ICE_CHECKING" ||
      voiceSystemState.webrtc === "peer_connecting" ||
      voiceSystemState.webrtc === "peer_created" ||
      voiceSystemState.stt === "connecting" ||
      voiceSystemState.tts === "connecting"
    ) {
      setVoiceState("initializing");
      return;
    }

    setVoiceState("initializing");
  }, [canUserSpeak, isVoiceActive, voiceSystemState]);

  return {
    voiceSystemState,
    canUserSpeak,
    voiceState,
  };
}
