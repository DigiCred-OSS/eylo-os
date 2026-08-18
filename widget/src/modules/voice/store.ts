import { BaseReactiveStore } from "@eylo/base/BaseReactiveStore";
import type { EyloStore } from "@eylo/store";
import type {
  RealtimeServiceState,
  TVoiceConnectionState,
  TVoiceState,
  VoiceRuntimeError,
  VoiceRuntimeMode,
  VoiceVendorServiceState,
  WebRTCServiceState,
} from "./types";

export type VoiceStoreState = {
  isSessionActive: boolean;
  connectionState: TVoiceConnectionState;
  runtimeMode: VoiceRuntimeMode;
  webrtcState: WebRTCServiceState | null;
  sttState: VoiceVendorServiceState | null;
  ttsState: VoiceVendorServiceState | null;
  realtimeState: RealtimeServiceState;
  sttVendor: string | null;
  ttsVendor: string | null;
  statusMessage: string | null;
  lastError: VoiceRuntimeError | null;
  interactionState: TVoiceState;
  interactionCallId: string | null;
  interactionCallStartedAt: number | null;
  interactionSequence: number;
  remoteStream: MediaStream | null;
  localStream: MediaStream | null;
};

class VoiceStore extends BaseReactiveStore<VoiceStoreState> {
  private static _instance: VoiceStore | null = null;

  constructor(parent: EyloStore) {
    if (VoiceStore._instance) {
      return VoiceStore._instance;
    }
    const initialState: VoiceStoreState = {
      isSessionActive: false,
      connectionState: "DISCONNECTED",
      runtimeMode: "browser_decomposed",
      webrtcState: null,
      sttState: null,
      ttsState: null,
      realtimeState: "inactive",
      sttVendor: null,
      ttsVendor: null,
      statusMessage: null,
      lastError: null,
      interactionState: "INACTIVE",
      interactionCallId: null,
      interactionCallStartedAt: null,
      interactionSequence: 0,
      remoteStream: null,
      localStream: null,
    };
    super(initialState, "eylo:voice:");
    void parent;
    VoiceStore._instance = this;
  }
}

export { VoiceStore };
