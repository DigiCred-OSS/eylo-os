import { EYLO_EVENTS } from "@eylo/events";
import { WS_ACTIONS } from "@eylo/net/constants";
import type { TWsEventActionValue } from "@eylo/net/types";
import type { EyloStore } from "@eylo/store";
import { logger } from "@eylo/utils";

import { AudioProcessor } from "./audio-processor.service";
import { requireVoiceBrowserCapabilities } from "./browser-capabilities";
import { AUDIO_PROCESSOR_CONFIG } from "./config";
import { VoiceConnectionStateMachine, VoiceVendorStateMachine } from "./state-machine";
import type {
  TVoiceConnectionState,
  TVoiceState,
  VoiceInteractionPayload,
  VoiceRuntimeError,
  VoiceSession,
  VoiceVendorLifecyclePayload,
  VoiceVendorServiceState,
  WebRTCLifecyclePayload,
  WebRTCServiceState,
} from "./types";

type WebRTCStateEvent =
  | typeof EYLO_EVENTS.WEBRTC_PEER_CREATED
  | typeof EYLO_EVENTS.WEBRTC_PEER_CONNECTING
  | typeof EYLO_EVENTS.WEBRTC_PEER_CONNECTED
  | typeof EYLO_EVENTS.WEBRTC_PEER_DISCONNECTED
  | typeof EYLO_EVENTS.WEBRTC_PEER_FAILED
  | typeof EYLO_EVENTS.WEBRTC_ICE_GATHERING
  | typeof EYLO_EVENTS.WEBRTC_ICE_COMPLETE
  | typeof EYLO_EVENTS.WEBRTC_TRACK_ADDED
  | typeof EYLO_EVENTS.WEBRTC_TRACK_REMOVED;

type WebRTCLifecycleHandler = {
  action: TWsEventActionValue;
  event: WebRTCStateEvent;
  label: string;
  state: WebRTCServiceState;
};

type VendorStateEvent =
  | typeof EYLO_EVENTS.STT_CONNECTING
  | typeof EYLO_EVENTS.STT_CONNECTED
  | typeof EYLO_EVENTS.STT_READY
  | typeof EYLO_EVENTS.STT_DISCONNECTED
  | typeof EYLO_EVENTS.STT_ERROR
  | typeof EYLO_EVENTS.TTS_CONNECTING
  | typeof EYLO_EVENTS.TTS_CONNECTED
  | typeof EYLO_EVENTS.TTS_READY
  | typeof EYLO_EVENTS.TTS_DISCONNECTED
  | typeof EYLO_EVENTS.TTS_ERROR;

type VendorLifecycleHandler = {
  action: TWsEventActionValue;
  event: VendorStateEvent;
  label: string;
  source: "stt" | "tts";
  state: VoiceVendorServiceState;
};

type WebRTCPreparedConfig = {
  protocol_version: 1;
  negotiation_id: string;
  negotiation_expires_at: number;
  credential_expires_at: number | null;
  iceServers: RTCIceServer[];
};

type PendingWebRTCPrepare = {
  resolve: (config: WebRTCPreparedConfig) => void;
  reject: (error: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
};

type PendingAudioConfig = {
  requestId: string;
  resolve: () => void;
  reject: (error: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
};

const WEBRTC_PROTOCOL_VERSION = 1 as const;
const WEBRTC_PREPARE_TIMEOUT_MS = 30_000;
const AUDIO_CONFIG_TIMEOUT_MS = 30_000;

export class VoiceStartCancelledError extends Error {
  constructor() {
    super("Voice session start was cancelled");
    this.name = "VoiceStartCancelledError";
  }
}

const WEBRTC_LIFECYCLE_HANDLERS: WebRTCLifecycleHandler[] = [
  {
    action: WS_ACTIONS.WEBRTC_PEER_CREATED,
    event: EYLO_EVENTS.WEBRTC_PEER_CREATED,
    label: "WebRTC peer created",
    state: "peer_created",
  },
  {
    action: WS_ACTIONS.WEBRTC_PEER_CONNECTING,
    event: EYLO_EVENTS.WEBRTC_PEER_CONNECTING,
    label: "WebRTC peer connecting",
    state: "peer_connecting",
  },
  {
    action: WS_ACTIONS.WEBRTC_PEER_CONNECTED,
    event: EYLO_EVENTS.WEBRTC_PEER_CONNECTED,
    label: "WebRTC peer connected",
    state: "peer_connected",
  },
  {
    action: WS_ACTIONS.WEBRTC_PEER_DISCONNECTED,
    event: EYLO_EVENTS.WEBRTC_PEER_DISCONNECTED,
    label: "WebRTC peer disconnected",
    state: "peer_disconnected",
  },
  {
    action: WS_ACTIONS.WEBRTC_PEER_FAILED,
    event: EYLO_EVENTS.WEBRTC_PEER_FAILED,
    label: "WebRTC peer failed",
    state: "peer_failed",
  },
  {
    action: WS_ACTIONS.WEBRTC_ICE_GATHERING,
    event: EYLO_EVENTS.WEBRTC_ICE_GATHERING,
    label: "WebRTC ICE gathering",
    state: "ice_gathering",
  },
  {
    action: WS_ACTIONS.WEBRTC_ICE_COMPLETE,
    event: EYLO_EVENTS.WEBRTC_ICE_COMPLETE,
    label: "WebRTC ICE complete",
    state: "ice_complete",
  },
  {
    action: WS_ACTIONS.WEBRTC_TRACK_ADDED,
    event: EYLO_EVENTS.WEBRTC_TRACK_ADDED,
    label: "WebRTC track added",
    state: "track_added",
  },
  {
    action: WS_ACTIONS.WEBRTC_TRACK_REMOVED,
    event: EYLO_EVENTS.WEBRTC_TRACK_REMOVED,
    label: "WebRTC track removed",
    state: "track_removed",
  },
];

const VENDOR_LIFECYCLE_HANDLERS: VendorLifecycleHandler[] = [
  {
    action: WS_ACTIONS.STT_CONNECTING,
    event: EYLO_EVENTS.STT_CONNECTING,
    label: "STT connecting",
    source: "stt",
    state: "connecting",
  },
  {
    action: WS_ACTIONS.STT_CONNECTED,
    event: EYLO_EVENTS.STT_CONNECTED,
    label: "STT connected",
    source: "stt",
    state: "connected",
  },
  {
    action: WS_ACTIONS.STT_READY,
    event: EYLO_EVENTS.STT_READY,
    label: "STT ready",
    source: "stt",
    state: "ready",
  },
  {
    action: WS_ACTIONS.STT_DISCONNECTED,
    event: EYLO_EVENTS.STT_DISCONNECTED,
    label: "STT disconnected",
    source: "stt",
    state: "disconnected",
  },
  {
    action: WS_ACTIONS.STT_ERROR,
    event: EYLO_EVENTS.STT_ERROR,
    label: "STT error",
    source: "stt",
    state: "error",
  },
  {
    action: WS_ACTIONS.TTS_CONNECTING,
    event: EYLO_EVENTS.TTS_CONNECTING,
    label: "TTS connecting",
    source: "tts",
    state: "connecting",
  },
  {
    action: WS_ACTIONS.TTS_CONNECTED,
    event: EYLO_EVENTS.TTS_CONNECTED,
    label: "TTS connected",
    source: "tts",
    state: "connected",
  },
  {
    action: WS_ACTIONS.TTS_READY,
    event: EYLO_EVENTS.TTS_READY,
    label: "TTS ready",
    source: "tts",
    state: "ready",
  },
  {
    action: WS_ACTIONS.TTS_DISCONNECTED,
    event: EYLO_EVENTS.TTS_DISCONNECTED,
    label: "TTS disconnected",
    source: "tts",
    state: "disconnected",
  },
  {
    action: WS_ACTIONS.TTS_ERROR,
    event: EYLO_EVENTS.TTS_ERROR,
    label: "TTS error",
    source: "tts",
    state: "error",
  },
];

export class VoiceService {
  private static _instance: VoiceService | undefined;
  private _eyloStore: EyloStore;
  private _currentSession: VoiceSession | null = null;
  private _audioProcessor: AudioProcessor;
  private _stateMachine: VoiceConnectionStateMachine;
  private _sttStateMachine: VoiceVendorStateMachine;
  private _ttsStateMachine: VoiceVendorStateMachine;
  // Queue ICE candidates that arrive before the remote description is set
  private _pendingIceCandidates: RTCIceCandidateInit[] = [];
  private _isAudioInitialized: boolean = false;
  private _peerConnection: RTCPeerConnection | null = null;
  private _remoteStream: MediaStream | null = null;
  private _localStream: MediaStream | null = null;
  private _conversationId: string | null = null;
  private _isCleaningUp: boolean = false; // Prevent duplicate cleanup
  private _startSessionPromise: Promise<void> | null = null;
  private _startCancellationRequested: boolean = false;
  private _webrtcPreparedConfig: WebRTCPreparedConfig | null = null;
  private _pendingWebRTCPrepare: PendingWebRTCPrepare | null = null;
  private _pendingAudioConfig: PendingAudioConfig | null = null;
  private _latestVoiceCallStartedAt = 0;

  constructor(eyloStore: EyloStore) {
    this._eyloStore = eyloStore;
    this._audioProcessor = new AudioProcessor(AUDIO_PROCESSOR_CONFIG);
    this._stateMachine = new VoiceConnectionStateMachine();
    this._sttStateMachine = new VoiceVendorStateMachine("stt");
    this._ttsStateMachine = new VoiceVendorStateMachine("tts");

    if (!VoiceService._instance) {
      this._setupWebRTCHandlers();
      this._eyloStore.ee.on(EYLO_EVENTS.ERROR, this._handleAudioConfigError);
      VoiceService._instance = this;
    }

    return VoiceService._instance;
  }

  /**
   * Update the connection state using the state machine
   * This ensures only valid transitions occur and provides centralized logging
   */
  private _updateConnectionState(state: TVoiceConnectionState, reason?: string): void {
    // Attempt state transition
    const success = this._stateMachine.transition(state, reason);

    if (success) {
      // Update session state
      if (this._currentSession) {
        this._currentSession.connectionState = this._stateMachine.currentState;
      }

      // Update store (for UI)
      this._eyloStore.voiceStore.set("connectionState", this._stateMachine.currentState);
      this._eyloStore.voiceStore.set("statusMessage", reason ?? null);
      // TODO (best practices): emit a structured telemetry event here so backend logs can be correlated with client-side state transitions, improving cross-system observability when diagnosing call issues.
    }
  }

  private _setWebRTCState(state: WebRTCServiceState, payload: WebRTCLifecyclePayload): void {
    this._eyloStore.voiceStore.set("webrtcState", state);
    this._eyloStore.voiceStore.set("statusMessage", payload.message ?? null);

    if (state === "peer_failed") {
      this._setVoiceError({
        source: "webrtc",
        message: payload.message ?? "WebRTC connection failed",
      });
    }
  }

  private _setVendorState(
    source: "stt" | "tts",
    state: VoiceVendorServiceState,
    payload: VoiceVendorLifecyclePayload
  ): void {
    const stateKey = source === "stt" ? "sttState" : "ttsState";
    const vendorKey = source === "stt" ? "sttVendor" : "ttsVendor";
    const stateMachine = source === "stt" ? this._sttStateMachine : this._ttsStateMachine;
    const transition = stateMachine.transition(state);

    if (!transition.changed) {
      return;
    }

    this._eyloStore.voiceStore.set(stateKey, transition.state);
    this._eyloStore.voiceStore.set(vendorKey, payload.vendor ?? null);
    this._eyloStore.voiceStore.set("statusMessage", payload.message ?? null);

    if (payload.runtime_mode === "browser_realtime" && state === "ready") {
      this._eyloStore.voiceStore.set("runtimeMode", "browser_realtime");
      this._eyloStore.voiceStore.set("realtimeState", "ready");
    }

    if (state === "error") {
      this._setVoiceError({
        source: payload.runtime_mode === "browser_realtime" ? "realtime" : source,
        message: payload.message ?? `${source.toUpperCase()} service error`,
      });
    }
  }

  private _setVoiceError(error: VoiceRuntimeError): void {
    this._eyloStore.voiceStore.set("lastError", error);
    if (error.source === "realtime") {
      this._eyloStore.voiceStore.set("realtimeState", "error");
    }
  }

  private _setInteractionState(payload: VoiceInteractionPayload): void {
    const validStates: TVoiceState[] = [
      "INACTIVE",
      "INITIALIZING",
      "LISTENING",
      "PROCESSING",
      "SPEAKING",
      "ERROR",
    ];
    if (
      !payload.voice_call_id ||
      !Number.isFinite(payload.call_started_at) ||
      !Number.isInteger(payload.sequence) ||
      !validStates.includes(payload.state)
    ) {
      logger.warn("Ignoring malformed voice interaction state", payload);
      return;
    }
    if (!this._currentSession || payload.call_started_at < this._latestVoiceCallStartedAt) {
      return;
    }

    const voiceStore = this._eyloStore.voiceStore;
    const currentCallId = voiceStore.get("interactionCallId");
    const currentSequence = voiceStore.get("interactionSequence");
    if (currentCallId === payload.voice_call_id && payload.sequence <= currentSequence) {
      return;
    }

    this._latestVoiceCallStartedAt = Math.max(
      this._latestVoiceCallStartedAt,
      payload.call_started_at
    );
    voiceStore.set("interactionCallId", payload.voice_call_id);
    voiceStore.set("interactionCallStartedAt", payload.call_started_at);
    voiceStore.set("interactionSequence", payload.sequence);
    voiceStore.set("interactionState", payload.state);
    this._currentSession.state = payload.state;
    if (payload.state === "ERROR") {
      this._setVoiceError({ source: "realtime", message: "Voice runtime failed" });
    }
  }

  private _resetRuntimeReadiness(): void {
    this._sttStateMachine.reset();
    this._ttsStateMachine.reset();
    this._eyloStore.voiceStore.set("runtimeMode", "browser_decomposed");
    this._eyloStore.voiceStore.set("webrtcState", null);
    this._eyloStore.voiceStore.set("sttState", null);
    this._eyloStore.voiceStore.set("ttsState", null);
    this._eyloStore.voiceStore.set("realtimeState", "inactive");
    this._eyloStore.voiceStore.set("sttVendor", null);
    this._eyloStore.voiceStore.set("ttsVendor", null);
    this._eyloStore.voiceStore.set("statusMessage", null);
    this._eyloStore.voiceStore.set("lastError", null);
    this._eyloStore.voiceStore.set("interactionState", "INACTIVE");
    this._eyloStore.voiceStore.set("interactionCallId", null);
    this._eyloStore.voiceStore.set("interactionCallStartedAt", null);
    this._eyloStore.voiceStore.set("interactionSequence", 0);
  }

  private _getIceCandidateInit(data: unknown): RTCIceCandidateInit | undefined {
    if (!data || typeof data !== "object") return undefined;

    if ("candidate" in data) {
      const wrappedCandidate = (data as { candidate?: unknown }).candidate;
      if (typeof wrappedCandidate === "string") {
        return data as RTCIceCandidateInit;
      }
      return wrappedCandidate && typeof wrappedCandidate === "object"
        ? (wrappedCandidate as RTCIceCandidateInit)
        : undefined;
    }

    return data as RTCIceCandidateInit;
  }

  /**
   * Get current connection state
   */
  public getConnectionState(): TVoiceConnectionState {
    return this._stateMachine.currentState;
  }

  /**
   * Get state transition history (useful for debugging)
   */
  public getStateHistory(): string {
    return this._stateMachine.getHistoryLog();
  }

  private _normalizeHangupReason(reason?: string): string {
    if (!reason) {
      logger.warn('[VoiceService] Hangup reason missing; defaulting to "unknown"');
      return "unknown";
    }

    const sanitized = reason.trim().toLowerCase();

    if (!sanitized) {
      logger.warn('[VoiceService] Hangup reason empty after trim; defaulting to "unknown"');
      return "unknown";
    }

    if (sanitized.includes("user")) {
      return "user_initiated";
    }

    if (sanitized.includes("ice")) {
      return "ice_connection_issue";
    }

    if (sanitized.includes("peer")) {
      return "peer_connection_issue";
    }

    const normalized = sanitized.replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

    if (!normalized) {
      logger.warn(
        '[VoiceService] Hangup reason normalized to empty string; defaulting to "unknown"'
      );
      return "unknown";
    }

    if (normalized === "unknown") {
      logger.warn('[VoiceService] Hangup reason normalized to generic "unknown" token', {
        originalReason: reason,
      });
    }

    return normalized;
  }

  private _sendWebRTCHangup(reason?: string) {
    this._eyloStore.cm.send({
      kind: WS_ACTIONS.WEBRTC_HANGUP,
      data: {
        protocol_version: WEBRTC_PROTOCOL_VERSION,
        negotiation_id: this._webrtcPreparedConfig?.negotiation_id,
        conversation_id: this._conversationId,
        reason: this._normalizeHangupReason(reason),
      },
    });
  }

  public async endVoiceCall(
    reason: string = "User ended call",
    options: { notifyServer?: boolean } = {}
  ): Promise<void> {
    const { notifyServer = true } = options;

    if (this._startSessionPromise) {
      this._startCancellationRequested = true;
      logger.debug("[VoiceService] Cancelling ongoing session start before cleanup...");
    }

    // Prevent duplicate cleanup - critical for avoiding race conditions
    if (this._isCleaningUp) {
      logger.debug("[VoiceService] Cleanup already in progress, ignoring duplicate call...");
      return;
    }

    // If already cleaned up completely
    if (!this._currentSession && !this._peerConnection && !this._localStream) {
      logger.debug(
        "[VoiceService] Already cleaned up (no session, no peer, no stream), skipping..."
      );
      return;
    }

    // Set flag to prevent re-entry
    this._isCleaningUp = true;
    logger.debug("[VoiceService] Ending voice call...", {
      hasSession: !!this._currentSession,
      hasPeer: !!this._peerConnection,
      hasLocalStream: !!this._localStream,
      hasRemoteStream: !!this._remoteStream,
    });

    try {
      // Send hangup signal to server with contextual reason
      if (notifyServer) {
        this._sendWebRTCHangup(reason);
      }

      // STEP 1: Stop all media tracks FIRST (microphone and speakers)
      // This must happen before audio processor cleanup to ensure tracks are released
      logger.debug("[VoiceService] Stopping media tracks...");

      // Stop tracks from peer connection senders (these hold references to tracks)
      if (this._peerConnection) {
        const senders = this._peerConnection.getSenders();
        logger.debug(`[VoiceService] Found ${senders.length} peer connection senders to remove`);
        senders.forEach((sender) => {
          if (sender.track) {
            const track = sender.track;
            const trackBeforeState = track.readyState;
            logger.debug(
              `[VoiceService] Stopping and removing sender track: ${track.kind}, readyState: ${trackBeforeState}, id: ${track.id}`
            );

            track.stop();
            const trackAfterState = track.readyState;

            this._peerConnection?.removeTrack(sender); // Explicitly remove track from peer connection

            logger.debug(
              `[VoiceService] Sender track after stop/remove: readyState changed from ${trackBeforeState} to ${trackAfterState}`
            );
          }
        });
      }

      // Stop local streams (microphone) - CRITICAL for releasing mic
      if (this._localStream) {
        const tracks = this._localStream.getTracks();
        logger.debug(`[VoiceService] Found ${tracks.length} local stream tracks`);
        tracks.forEach((track) => {
          logger.debug(
            `[VoiceService] Stopping local track: ${track.kind}, enabled: ${track.enabled}, readyState: ${track.readyState}, label: ${track.label}`
          );
          track.stop();
          logger.debug(`[VoiceService] After stop - readyState: ${track.readyState}`);
        });
        this._localStream = null;
      }

      // Stop remote streams (headphones/speakers)
      if (this._remoteStream) {
        const tracks = this._remoteStream.getTracks();
        logger.debug(`[VoiceService] Found ${tracks.length} remote stream tracks`);
        tracks.forEach((track) => {
          logger.debug(
            `[VoiceService] Stopping remote track: ${track.kind}, readyState: ${track.readyState}`
          );
          track.stop();
        });
        this._remoteStream = null;
      }

      // STEP 2: Cleanup audio processor (disconnect nodes and AWAIT context close)
      // CRITICAL: Must await to ensure AudioContext is fully closed and releases microphone
      await this._audioProcessor.cleanup();

      // Reset audio initialization flag so next call reinitializes
      this._isAudioInitialized = false;

      // STEP 3: Remove event handlers before closing peer connection
      if (this._peerConnection) {
        // Remove all event handlers to prevent them from firing during/after close
        this._peerConnection.onicecandidate = null;
        this._peerConnection.oniceconnectionstatechange = null;
        this._peerConnection.onconnectionstatechange = null;
        this._peerConnection.ontrack = null;

        this._peerConnection.close();
        this._peerConnection = null;
      }

      // STEP 4: Clear state
      this._pendingIceCandidates = [];
      this._webrtcPreparedConfig = null;
      if (this._pendingWebRTCPrepare) {
        clearTimeout(this._pendingWebRTCPrepare.timeout);
        this._pendingWebRTCPrepare.reject(new Error("WebRTC preparation cancelled"));
        this._pendingWebRTCPrepare = null;
      }
      if (this._pendingAudioConfig) {
        clearTimeout(this._pendingAudioConfig.timeout);
        this._pendingAudioConfig.reject(new Error("Audio configuration cancelled"));
        this._pendingAudioConfig = null;
      }
      this._conversationId = null;
      this._currentSession = null;

      // STEP 5: Update voice store state
      this._updateConnectionState("DISCONNECTED", reason);
      this._eyloStore.voiceStore.set("isSessionActive", false);
      this._eyloStore.voiceStore.set("remoteStream", null);
      this._eyloStore.voiceStore.set("localStream", null);
      this._resetRuntimeReadiness();

      logger.debug("[VoiceService] Voice call ended and resources cleaned up");
    } catch (err) {
      logger.error("[VoiceService] Error while cleaning up voice call:", err);
      throw err;
    } finally {
      // STEP 6: Final verification - check if there are any active tracks
      // This helps debug if Chrome still shows mic in use
      setTimeout(() => {
        logger.debug("[VoiceService] Post-cleanup verification:");
        logger.debug("  - Local stream:", this._localStream);
        logger.debug("  - Remote stream:", this._remoteStream);
        logger.debug("  - Peer connection:", this._peerConnection);
        logger.debug("  - Current session:", this._currentSession);
        logger.debug("  - Cleanup flag:", this._isCleaningUp);

        // CRITICAL: Check if Chrome still thinks we have active media
        // Open Chrome DevTools > Console and run: navigator.mediaDevices.enumerateDevices()
        // Then check chrome://media-internals to see active streams
        logger.debug("✅ To verify mic is released in Chrome:");
        logger.debug("   1. Check tab/address bar for microphone icon (should be gone)");
        logger.debug("   2. Visit chrome://media-internals and check for active streams");
        logger.debug('   3. All tracks should show readyState: "ended"');
      }, 100);

      // Reset cleanup flag
      this._isCleaningUp = false;
    }
  }

  public hasActiveSession(): boolean {
    return this._eyloStore.voiceStore.get("isSessionActive") ?? false;
  }

  private _registerWebRTCLifecycleHandler(handler: WebRTCLifecycleHandler): void {
    this._eyloStore.cm.registerMessageHandler(handler.action, (message) => {
      logger.debug(`[VoiceService] ${handler.label}`, message.data);
      const payload = message.data as WebRTCLifecyclePayload;
      this._setWebRTCState(handler.state, payload);
      this._eyloStore.ee.emit(handler.event, payload);
    });
  }

  private _registerVendorLifecycleHandler(handler: VendorLifecycleHandler): void {
    this._eyloStore.cm.registerMessageHandler(handler.action, (message) => {
      logger.debug(`[VoiceService] ${handler.label}`, message.data);
      const payload = message.data as VoiceVendorLifecyclePayload;
      this._setVendorState(handler.source, handler.state, payload);
      this._eyloStore.ee.emit(handler.event, payload);
      if (handler.state === "error" && this._currentSession) {
        return this.endVoiceCall(`${handler.source.toUpperCase()} service failed`);
      }
    });
  }

  private _setupWebRTCHandlers(): void {
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.AUDIO_CONFIG, (message) => {
      this._handleAudioConfigResponse(message);
    });
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.VOICE_STATE, (message) => {
      this._setInteractionState(message.data as VoiceInteractionPayload);
    });

    // Register WebRTC message handlers
    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.WEBRTC_PREPARE, (message) => {
      this._handleWebRTCPrepare(message.data);
    });

    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.WEBRTC_OFFER, (message) => {
      return this._handleWebRTCOffer(message.data);
    });

    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.WEBRTC_ANSWER, (message) => {
      const payload = message.data as {
        protocol_version?: number;
        outcome?: string;
        negotiation_id?: string;
        code?: string;
        sdp?: string;
      };
      if (typeof payload.sdp === "string") {
        this._eyloStore.ee.emit(EYLO_EVENTS.WEBRTC_ANSWER, { sdp: payload.sdp });
      }
      return this._handleWebRTCAnswer(payload);
    });

    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.WEBRTC_CANDIDATE, (message) => {
      return this._handleWebRTCCandidate(message.data);
    });

    this._eyloStore.cm.registerMessageHandler(WS_ACTIONS.WEBRTC_HANGUP, (message) => {
      return this._handleWebRTCHangup(message.data);
    });

    WEBRTC_LIFECYCLE_HANDLERS.forEach((handler) => this._registerWebRTCLifecycleHandler(handler));
    VENDOR_LIFECYCLE_HANDLERS.forEach((handler) => this._registerVendorLifecycleHandler(handler));
  }

  private _handleAudioConfigResponse = (message: any): void => {
    const pending = this._pendingAudioConfig;
    if (!pending || message.requestId !== pending.requestId) return;
    clearTimeout(pending.timeout);
    this._pendingAudioConfig = null;
    if (message.data?.initialized !== true) {
      pending.reject(new Error("Malformed audio configuration response"));
      return;
    }
    pending.resolve();
  };

  private _handleAudioConfigError = (message: any): void => {
    const pending = this._pendingAudioConfig;
    if (!pending || message?.requestId !== pending.requestId) return;
    clearTimeout(pending.timeout);
    this._pendingAudioConfig = null;
    pending.reject(new Error(message?.data?.message || "Voice initialization failed"));
  };

  private _configureAudio(conversationId: string): Promise<void> {
    if (this._pendingAudioConfig) {
      return Promise.reject(new Error("Audio configuration already in progress"));
    }
    const requestId = crypto.randomUUID();
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        if (this._pendingAudioConfig?.requestId === requestId) {
          this._pendingAudioConfig = null;
          reject(new Error("Audio configuration timed out"));
        }
      }, AUDIO_CONFIG_TIMEOUT_MS);
      this._pendingAudioConfig = { requestId, resolve, reject, timeout };
      const sent = this._eyloStore.cm.send({
        kind: WS_ACTIONS.AUDIO_CONFIG,
        requestId,
        data: {
          sample_rate: this._audioProcessor.inputContext?.sampleRate,
          encoding: "LINEAR16",
          channels: 1,
          language: "en-US",
          conversation_id: conversationId,
        },
      });
      if (!sent) {
        clearTimeout(timeout);
        this._pendingAudioConfig = null;
        reject(new Error("Audio configuration request was not sent"));
      }
    });
  }

  private _handleWebRTCPrepare(data: unknown): void {
    const pending = this._pendingWebRTCPrepare;
    if (!pending) return;
    clearTimeout(pending.timeout);
    this._pendingWebRTCPrepare = null;

    const payload =
      (data as {
        protocol_version?: number;
        outcome?: string;
        negotiation_id?: string;
        negotiation_expires_at?: number;
        credential_expires_at?: number | null;
        iceServers?: RTCIceServer[];
        code?: string;
      }) ?? {};
    if (payload.outcome !== "accepted") {
      pending.reject(new Error(`WebRTC preparation rejected: ${payload.code ?? "unknown"}`));
      return;
    }
    if (
      payload.protocol_version !== WEBRTC_PROTOCOL_VERSION ||
      typeof payload.negotiation_id !== "string" ||
      typeof payload.negotiation_expires_at !== "number" ||
      !Array.isArray(payload.iceServers)
    ) {
      pending.reject(new Error("Malformed WebRTC preparation response"));
      return;
    }
    const now = Date.now() / 1000;
    if (
      payload.negotiation_expires_at <= now ||
      (typeof payload.credential_expires_at === "number" && payload.credential_expires_at <= now)
    ) {
      pending.reject(new Error("WebRTC preparation credentials expired"));
      return;
    }

    const prepared: WebRTCPreparedConfig = {
      protocol_version: WEBRTC_PROTOCOL_VERSION,
      negotiation_id: payload.negotiation_id,
      negotiation_expires_at: payload.negotiation_expires_at,
      credential_expires_at: payload.credential_expires_at ?? null,
      iceServers: payload.iceServers,
    };
    this._webrtcPreparedConfig = prepared;
    pending.resolve(prepared);
  }

  private _prepareWebRTC(conversationId: string): Promise<WebRTCPreparedConfig> {
    if (this._webrtcPreparedConfig) return Promise.resolve(this._webrtcPreparedConfig);
    if (this._pendingWebRTCPrepare) {
      return Promise.reject(new Error("WebRTC preparation already in progress"));
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        if (this._pendingWebRTCPrepare?.timeout === timeout) {
          this._pendingWebRTCPrepare = null;
          reject(new Error("WebRTC preparation timed out"));
        }
      }, WEBRTC_PREPARE_TIMEOUT_MS);
      this._pendingWebRTCPrepare = { resolve, reject, timeout };
      const sent = this._eyloStore.cm.send({
        kind: WS_ACTIONS.WEBRTC_PREPARE,
        data: {
          protocol_version: WEBRTC_PROTOCOL_VERSION,
          conversation_id: conversationId,
        },
      });
      if (!sent) {
        clearTimeout(timeout);
        this._pendingWebRTCPrepare = null;
        reject(new Error("WebRTC preparation request was not sent"));
      }
    });
  }

  private async _handleWebRTCOffer(data: unknown): Promise<void> {
    try {
      const payload =
        (data as {
          protocol_version?: number;
          outcome?: string;
          negotiation_id?: string;
          sdp?: string;
          type?: RTCSdpType;
          conversation_id?: string;
          iceServers?: RTCIceServer[];
        }) ?? {};

      if (!payload || typeof payload.sdp !== "string") {
        logger.warn("[VoiceService] Ignoring malformed WebRTC offer payload", payload);
        return;
      }
      const prepared = this._webrtcPreparedConfig;
      if (
        !prepared ||
        payload.protocol_version !== WEBRTC_PROTOCOL_VERSION ||
        payload.outcome !== "accepted" ||
        payload.negotiation_id !== prepared.negotiation_id
      ) {
        throw new Error("WebRTC offer is not part of the prepared negotiation");
      }

      const conversationId = payload.conversation_id ?? this._conversationId;
      if (!conversationId) {
        logger.warn("[VoiceService] Received WebRTC offer without conversation id, ignoring");
        return;
      }

      if (this._conversationId && conversationId !== this._conversationId) {
        logger.warn("[VoiceService] Received WebRTC offer for different conversation, ignoring", {
          current: this._conversationId,
          incoming: conversationId,
        });
        return;
      }

      if (!this._conversationId) {
        this._conversationId = conversationId;
      }

      // Ensure we have a peer connection ready to accept the remote description
      let newlyCreatedPeer = false;
      if (!this._peerConnection) {
        if (!this._localStream) {
          logger.warn("[VoiceService] No local stream available to answer remote offer, ignoring");
          return;
        }

        await this._createPeerConnection(conversationId, prepared.iceServers);
        newlyCreatedPeer = true;

        if (!this._peerConnection) {
          throw new Error("Failed to establish peer connection for incoming offer");
        }
      }

      if (newlyCreatedPeer && this._localStream) {
        this._localStream
          .getTracks()
          .forEach((track) => this._peerConnection?.addTrack(track, this._localStream!));
      }

      if (this._currentSession && this._peerConnection) {
        this._currentSession.peerConnection = this._peerConnection;
        this._currentSession.conversationId = conversationId;
      }

      const offer = new RTCSessionDescription({
        type: payload.type ?? "offer",
        sdp: payload.sdp,
      });

      await this._peerConnection!.setRemoteDescription(offer);

      // Apply any ICE candidates that arrived before the remote description was set
      if (this._pendingIceCandidates.length > 0) {
        logger.debug(
          `[VoiceService] Applying ${this._pendingIceCandidates.length} pending ICE candidates after remote offer`
        );
        for (const candidate of this._pendingIceCandidates) {
          try {
            await this._peerConnection!.addIceCandidate(new RTCIceCandidate(candidate));
          } catch (candidateError) {
            logger.error(
              "[VoiceService] Failed to add pending ICE candidate after offer",
              candidateError
            );
          }
        }
        this._pendingIceCandidates = [];
      }

      const answer = await this._peerConnection!.createAnswer();
      await this._peerConnection!.setLocalDescription(answer);

      this._updateConnectionState("NEGOTIATING", "Responding to remote offer");

      this._eyloStore.cm.send({
        kind: WS_ACTIONS.WEBRTC_ANSWER,
        data: {
          protocol_version: WEBRTC_PROTOCOL_VERSION,
          negotiation_id: prepared.negotiation_id,
          sdp: answer.sdp!,
          type: answer.type,
          conversation_id: conversationId,
        },
      });
    } catch (err) {
      logger.error("[VoiceService] Error handling remote WebRTC offer:", err);
      // Remote renegotiation failed, attempt graceful cleanup to recover
      this.endVoiceCall("Remote offer handling failed").catch((cleanupErr) =>
        logger.error("[VoiceService] Error during cleanup after offer failure:", cleanupErr)
      );
    }
  }

  private async _handleWebRTCAnswer(data: {
    protocol_version?: number;
    outcome?: string;
    negotiation_id?: string;
    code?: string;
    sdp?: string;
  }): Promise<void> {
    try {
      if (data.outcome === "rejected") {
        throw new Error(`WebRTC offer rejected: ${data.code ?? "unknown"}`);
      }
      if (
        data.protocol_version !== WEBRTC_PROTOCOL_VERSION ||
        data.negotiation_id !== this._webrtcPreparedConfig?.negotiation_id ||
        typeof data.sdp !== "string"
      ) {
        throw new Error("WebRTC answer does not match the active negotiation");
      }
      // Need an active session + peer connection to apply the answer
      if (!this._currentSession?.peerConnection) return;

      const pc = this._currentSession.peerConnection;

      const answer = new RTCSessionDescription({
        type: "answer",
        sdp: data.sdp,
      });
      await pc.setRemoteDescription(answer);

      // Flush any ICE candidates that arrived before the answer
      if (this._pendingIceCandidates.length > 0) {
        for (const c of this._pendingIceCandidates) {
          try {
            await pc.addIceCandidate(new RTCIceCandidate(c));
          } catch (e) {
            console.error("Error adding pending ICE candidate:", e, c);
          }
        }
        this._pendingIceCandidates = [];
      }

      // We can now receive remote media; mark state accordingly
      this._currentSession.state = "LISTENING";
    } catch (err) {
      logger.error("[VoiceService] Error handling WebRTC answer", err);
      await this.endVoiceCall("WebRTC answer failed");
    }
  }

  private async _handleWebRTCCandidate(data: unknown): Promise<void> {
    try {
      const signaling = data as {
        outcome?: string;
        code?: string;
        negotiation_id?: string;
        candidate?: unknown;
      };
      if (
        signaling?.negotiation_id &&
        signaling.negotiation_id !== this._webrtcPreparedConfig?.negotiation_id
      ) {
        logger.warn("[VoiceService] Ignoring candidate for another negotiation");
        return;
      }
      if (signaling?.outcome && !("candidate" in signaling)) {
        if (signaling.outcome === "rejected") {
          logger.warn("[VoiceService] Remote ICE candidate rejected", {
            code: signaling.code ?? "unknown",
          });
        }
        return;
      }
      if (!this._currentSession?.peerConnection) return;
      const pc = this._currentSession.peerConnection;
      if ("candidate" in signaling && signaling.candidate === null) {
        await pc.addIceCandidate(null);
        return;
      }

      const candidateInit = this._getIceCandidateInit(data);

      if (!candidateInit || typeof candidateInit.candidate !== "string") {
        console.warn("Invalid ICE candidate payload:", data);
        return;
      }

      // If remote description isn't set yet, queue candidate to add later
      if (!pc.remoteDescription) {
        this._pendingIceCandidates.push(candidateInit);
        return;
      }

      await pc.addIceCandidate(new RTCIceCandidate(candidateInit));
    } catch (err) {
      console.error("Error handling WebRTC ICE candidate:", err);
    }
  }

  private async _handleWebRTCHangup(data: unknown): Promise<void> {
    try {
      const payload = (data as { reason?: string; conversation_id?: string }) ?? {};
      const reason = payload.reason ?? "Remote hangup";
      const incomingConversationId = payload.conversation_id;

      if (
        incomingConversationId &&
        this._conversationId &&
        incomingConversationId !== this._conversationId
      ) {
        logger.warn("[VoiceService] Received hangup for different conversation, ignoring", {
          current: this._conversationId,
          incoming: incomingConversationId,
        });
        return;
      }

      this._eyloStore.ee.emit(EYLO_EVENTS.WEBRTC_HANGUP, payload);

      await this.endVoiceCall(reason, { notifyServer: false });
    } catch (err) {
      logger.error("[VoiceService] Error handling remote hangup:", err);
    }
  }

  private async _createPeerConnection(
    conversationId: string,
    iceServers: RTCIceServer[]
  ): Promise<void> {
    // Any leftover ICE candidates from a prior session are no longer relevant
    this._pendingIceCandidates = [];

    const configuration: RTCConfiguration = {
      iceServers,
    };

    logger.debug("[VoiceService] Creating configured peer connection", {
      iceServerCount: iceServers.length,
    });

    this._peerConnection = new RTCPeerConnection(configuration);

    // Attach onicecandidate handler immediately to prevent race condition
    this._peerConnection.onicecandidate = (event) => {
      if (!event.candidate) {
        logger.debug("VOICE_SERVICE: ICE candidate gathering complete.");
        this._eyloStore.cm.send({
          kind: WS_ACTIONS.WEBRTC_CANDIDATE,
          data: {
            protocol_version: WEBRTC_PROTOCOL_VERSION,
            negotiation_id: this._webrtcPreparedConfig?.negotiation_id,
            candidate: null,
            conversation_id: conversationId,
          },
        });
        return;
      }

      if (this._isCleaningUp || !this._conversationId || this._conversationId !== conversationId) {
        logger.debug(
          "[VoiceService] Skipping ICE candidate send (cleanup in progress or conversation mismatch)",
          {
            isCleaningUp: this._isCleaningUp,
            currentConversation: this._conversationId,
            candidateConversation: conversationId,
          }
        );
        return;
      }
      this._eyloStore.cm.send({
        kind: WS_ACTIONS.WEBRTC_CANDIDATE,
        data: {
          protocol_version: WEBRTC_PROTOCOL_VERSION,
          negotiation_id: this._webrtcPreparedConfig?.negotiation_id,
          candidate: event.candidate.toJSON(),
          conversation_id: conversationId,
        },
      });
    };

    // Attach other event handlers for logging and state management
    this._peerConnection.oniceconnectionstatechange = () => {
      const iceState = this._peerConnection?.iceConnectionState;
      logger.debug(`VOICE_SERVICE: ICE connection state is ${iceState}`);

      // Map ICE connection state to our connection state
      switch (iceState) {
        case "checking":
          // Only transition to ICE_CHECKING if we're not already CONNECTED
          // ICE can continue checking even after we're connected (race condition)
          const currentState = this._stateMachine.currentState;
          if (currentState !== "CONNECTED") {
            this._updateConnectionState("ICE_CHECKING", "ICE candidates being checked");
          }
          break;
        case "connected":
        case "completed":
          // Don't set to CONNECTED yet - wait for ontrack event
          logger.debug("[VoiceService] ICE connected, waiting for remote track...");
          break;
        case "failed":
          // Only handle if we haven't already started cleanup
          if (this._currentSession) {
            this._updateConnectionState("FAILED", "ICE connection failed");
            logger.debug("[VoiceService] ICE connection failed, cleaning up...");
            // Fire and forget - event handlers don't need to await
            this.endVoiceCall("ICE connection failed").catch((err) =>
              console.error("[VoiceService] Error during ICE failure cleanup:", err)
            );
          }
          break;
        case "disconnected":
          if (this._currentSession) {
            this._updateConnectionState("FAILED", "ICE connection disconnected");
            this.endVoiceCall("ICE disconnected").catch((err) =>
              logger.error("[VoiceService] Error during ICE disconnect cleanup", err)
            );
          }
          break;
        case "closed":
          // Connection already cleaned up, just update state if needed
          const state = this._stateMachine.currentState;
          if (state !== "DISCONNECTED") {
            this._updateConnectionState("DISCONNECTED", "ICE connection closed");
          }
          break;
      }
    };

    this._peerConnection.onconnectionstatechange = () => {
      const connState = this._peerConnection?.connectionState;
      logger.debug(`VOICE_SERVICE: Connection state is ${connState}`);

      // Handle connection failure - only if we have an active session
      if (connState === "failed") {
        if (this._currentSession) {
          this._updateConnectionState("FAILED", "Peer connection failed");
          logger.debug("[VoiceService] Peer connection failed, cleaning up...");
          // Fire and forget - event handlers don't need to await
          this.endVoiceCall("Peer connection failed").catch((err) =>
            console.error("[VoiceService] Error during peer failure cleanup:", err)
          );
        }
      } else if (connState === "disconnected") {
        if (this._currentSession) {
          this._updateConnectionState("FAILED", "Peer connection disconnected");
          this.endVoiceCall("Peer disconnected").catch((err) =>
            logger.error("[VoiceService] Error during peer disconnect cleanup", err)
          );
        }
      } else if (connState === "closed") {
        // Connection already cleaned up, just update state if needed
        const state = this._stateMachine.currentState;
        if (state !== "DISCONNECTED") {
          this._updateConnectionState("DISCONNECTED", "Peer connection closed");
        }
      }
    };

    this._peerConnection.onsignalingstatechange = () => {
      logger.debug(`VOICE_SERVICE: Signaling state is ${this._peerConnection?.signalingState}`);
    };

    this._peerConnection.onicegatheringstatechange = () => {
      logger.debug(
        `VOICE_SERVICE: ICE gathering state is ${this._peerConnection?.iceGatheringState}`
      );
    };
    this._peerConnection.ontrack = (event) => {
      logger.debug("VOICE_SERVICE: Remote track received.");
      this._remoteStream = event.streams[0];
      this._eyloStore.voiceStore.set("remoteStream", this._remoteStream);
      this._audioProcessor.setupOutputProcessing(this._remoteStream);

      // Now we're truly connected - audio is flowing both ways
      this._updateConnectionState("CONNECTED", "Remote audio track received, audio flowing");
      logger.debug("[VoiceService] ✓ Connection fully established - ready for conversation");
    };
  }

  async startVoiceSession(conversationId: string): Promise<void> {
    if (this._startSessionPromise) {
      console.warn(
        "[VoiceService] Voice session start already in progress, awaiting existing start"
      );
      return this._startSessionPromise;
    }

    this._startCancellationRequested = false;
    const startPromise = this._startVoiceSessionInternal(conversationId);
    this._startSessionPromise = startPromise;

    try {
      await startPromise;
    } finally {
      if (this._startSessionPromise === startPromise) {
        this._startSessionPromise = null;
        this._startCancellationRequested = false;
      }
    }
  }

  private _throwIfStartCancelled(acquiredStream?: MediaStream): void {
    if (!this._startCancellationRequested) {
      return;
    }

    acquiredStream?.getTracks().forEach((track) => track.stop());
    throw new VoiceStartCancelledError();
  }

  private async _startVoiceSessionInternal(conversationId: string): Promise<void> {
    requireVoiceBrowserCapabilities(globalThis);

    // Check if session already exists
    if (this._currentSession) {
      console.warn("[VoiceService] Voice session already active, ignoring start request");
      throw new Error("Voice session already active");
    }

    // Check if already in an active state (other than DISCONNECTED)
    if (this._stateMachine.isActive()) {
      console.warn(
        `[VoiceService] State machine in active state: ${this._stateMachine.currentState}, cannot start new session`
      );
      throw new Error(`Cannot start session while in ${this._stateMachine.currentState} state`);
    }

    // Pre-create session so state updates have a target to sync against
    this._currentSession = {
      id: crypto.randomUUID(),
      conversationId,
      state: "INITIALIZING",
      connectionState: "DISCONNECTED",
      peerConnection: null,
      localStream: null,
    };
    this._eyloStore.voiceStore.set("isSessionActive", true);
    this._resetRuntimeReadiness();
    this._conversationId = conversationId;

    // Move to CONNECTING immediately so UI reflects microphone prompt latency
    this._updateConnectionState("CONNECTING", "Requesting microphone access");

    try {
      // Initialize audio processing
      if (!this._isAudioInitialized) {
        this._isAudioInitialized = await this._audioProcessor.initialize();
      }
      this._throwIfStartCancelled();

      // Get user media
      const localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          // deviceId
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 44100,
          sampleSize: 16,
        },
        video: false,
      });
      this._throwIfStartCancelled(localStream);
      this._localStream = localStream;

      // Setup input processing
      this._audioProcessor.setupInputProcessing(this._localStream);
      if (this._currentSession) {
        this._currentSession.localStream = this._localStream;
      }

      // Update store with local stream
      this._eyloStore.voiceStore.set("localStream", this._localStream);

      // Bind exact voice/provider config on the server before requesting ICE config.
      await this._configureAudio(conversationId);
      this._throwIfStartCancelled();

      const prepared = await this._prepareWebRTC(conversationId);
      this._throwIfStartCancelled();

      // Create peer connection
      await this._createPeerConnection(conversationId, prepared.iceServers);
      this._throwIfStartCancelled();
      if (!this._peerConnection) {
        throw new Error("Failed to create peer connection");
      }
      if (this._currentSession) {
        this._currentSession.peerConnection = this._peerConnection;
      }

      // Add local stream
      if (!this._localStream) {
        throw new Error("Failed to get local stream");
      }
      this._localStream
        .getTracks()
        .forEach((track) => this._peerConnection?.addTrack(track, this._localStream!));

      // Create offer
      const offer = await this._peerConnection!.createOffer();
      this._throwIfStartCancelled();
      await this._peerConnection!.setLocalDescription(offer);
      this._throwIfStartCancelled();

      // Send WebRTC offer
      this._eyloStore.cm.send({
        kind: WS_ACTIONS.WEBRTC_OFFER,
        data: {
          protocol_version: WEBRTC_PROTOCOL_VERSION,
          negotiation_id: prepared.negotiation_id,
          sdp: offer.sdp!,
          type: offer.type,
          conversation_id: conversationId,
          media_config: {
            audio_enabled: true,
            video_enabled: false,
            audio_codec: "opus",
            tts_sample_rate: 16_000,
            browser_upsampling: this._audioProcessor.isUpsamplingEnabled,
            input_context_rate: this._audioProcessor.inputContext?.sampleRate,
            output_context_rate: this._audioProcessor.outputContext?.sampleRate,
            echo_cancellation: true,
            noise_suppression: true,
          },
        },
      });

      // We are now negotiating the connection; transition accordingly
      this._updateConnectionState("NEGOTIATING", "WebRTC offer created and sent to server");
    } catch (error) {
      if (this._startCancellationRequested || error instanceof VoiceStartCancelledError) {
        throw new VoiceStartCancelledError();
      }
      console.error("Error starting voice session:", error);
      const message = error instanceof Error ? error.message : String(error);
      this._setVoiceError({
        source: "webrtc",
        message,
      });
      this._updateConnectionState("ERROR", `Session start failed: ${message}`);
      try {
        await this.endVoiceCall("Session start error");
      } catch (cleanupError) {
        console.error("[VoiceService] Error during session start cleanup:", cleanupError);
      }
      throw error;
    }
  }
}
