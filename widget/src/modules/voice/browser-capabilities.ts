export type VoiceBrowserCapabilityProblem =
  | "audio_context_unavailable"
  | "microphone_unavailable"
  | "webrtc_unavailable";

type VoiceBrowserHost = {
  AudioContext?: unknown;
  RTCPeerConnection?: unknown;
  navigator?: {
    mediaDevices?: {
      getUserMedia?: unknown;
    };
  };
};

const UNAVAILABLE_MESSAGE = "Voice needs a browser with microphone, Web Audio, and WebRTC support.";

export class VoiceStartUnavailableError extends Error {
  readonly code: VoiceBrowserCapabilityProblem;

  constructor(code: VoiceBrowserCapabilityProblem) {
    super(UNAVAILABLE_MESSAGE);
    this.name = "VoiceStartUnavailableError";
    this.code = code;
  }
}

export function voiceBrowserCapabilityProblem(
  host: VoiceBrowserHost
): VoiceBrowserCapabilityProblem | null {
  if (typeof host.AudioContext !== "function") {
    return "audio_context_unavailable";
  }
  if (typeof host.navigator?.mediaDevices?.getUserMedia !== "function") {
    return "microphone_unavailable";
  }
  if (typeof host.RTCPeerConnection !== "function") {
    return "webrtc_unavailable";
  }
  return null;
}

export function requireVoiceBrowserCapabilities(host: VoiceBrowserHost): void {
  const problem = voiceBrowserCapabilityProblem(host);
  if (problem) {
    throw new VoiceStartUnavailableError(problem);
  }
}
