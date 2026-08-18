// components/VoiceWaveform/index.tsx
import { type FC } from "preact/compat";
import { useEffect, useRef, useState } from "preact/hooks";
import styles from "./VoiceWaveform.module.css";
import { Text } from "../../design-system/components/Typography";
import type { VoiceSystemState, VoiceUiState } from "../../hooks/useVoiceSystemState";

export const getVoiceSystemStatus = (
  voiceSystemState: VoiceSystemState
): {
  message: string;
  type: "connecting" | "ready" | "error";
} => {
  const webrtcStatus = voiceSystemState.webrtc;
  const sttStatus = voiceSystemState.stt;
  const ttsStatus = voiceSystemState.tts;

  if (voiceSystemState.lastError) {
    return { message: voiceSystemState.lastError.message, type: "error" };
  }

  if (webrtcStatus === "peer_failed" || sttStatus === "error" || ttsStatus === "error") {
    return { message: "Voice connection failed", type: "error" };
  }

  if (
    webrtcStatus === "peer_disconnected" ||
    sttStatus === "disconnected" ||
    ttsStatus === "disconnected"
  ) {
    return { message: "Disconnected", type: "error" };
  }

  if (webrtcStatus === "peer_connected" && sttStatus === "ready" && ttsStatus === "ready") {
    return { message: "Connected", type: "ready" };
  }

  if (
    webrtcStatus === "peer_connecting" ||
    sttStatus === "connecting" ||
    ttsStatus === "connecting"
  ) {
    return { message: "Connecting voice...", type: "connecting" };
  }

  if (webrtcStatus === "peer_created") {
    return { message: "Establishing connection...", type: "connecting" };
  }

  if (webrtcStatus === "peer_connected" && sttStatus === "connected") {
    return { message: "Preparing microphone...", type: "connecting" };
  }

  if (webrtcStatus === "peer_connected" && sttStatus === "ready" && ttsStatus !== "ready") {
    return { message: "Preparing voice output...", type: "connecting" };
  }

  return { message: voiceSystemState.statusMessage ?? "Initializing...", type: "connecting" };
};
interface VoiceWaveformProps {
  voiceSystemState: VoiceSystemState;
  isActive?: boolean;
  status?: VoiceUiState;
  localStream?: MediaStream | null;
}

const VoiceWaveform: FC<VoiceWaveformProps> = ({
  voiceSystemState,
  isActive,
  status = "listening",
  localStream,
}) => {
  // Derive isActive from status if not explicitly provided
  const active = isActive ?? (status === "listening" || status === "connected");

  const barCount = 16; // Increased from 8 to 16 bars
  const [audioLevels, setAudioLevels] = useState<number[]>(Array(barCount).fill(0));
  const analyserRef = useRef<AnalyserNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    if (!active) {
      // Cleanup when inactive
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch((err) => {
          console.error("[VoiceWaveform] Error closing audio context:", err);
        });
        audioContextRef.current = null;
      }
      analyserRef.current = null;
      setAudioLevels(Array(barCount).fill(0));
      return;
    }

    // Setup audio analysis
    const setupAudioAnalysis = async () => {
      try {
        // Use provided localStream if available, otherwise get microphone access
        let stream = localStream;
        if (!stream) {
          stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          streamRef.current = stream;
        }

        // Create audio context and analyser
        const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
        const analyser = audioContext.createAnalyser();
        analyser.fftSize = 1024; // Increased for better frequency resolution with more bars
        analyser.smoothingTimeConstant = 0.3; // Reduced for more responsive animation

        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);

        audioContextRef.current = audioContext;
        analyserRef.current = analyser;

        // Start animation loop
        const updateLevels = () => {
          if (!analyserRef.current) return;

          const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
          analyserRef.current.getByteFrequencyData(dataArray);

          // Calculate frequency bands
          const bandSize = Math.floor(dataArray.length / barCount);
          const newLevels = [];

          for (let i = 0; i < barCount; i++) {
            const start = i * bandSize;
            const end = start + bandSize;
            const bandData = dataArray.slice(start, end);
            const average = bandData.reduce((a, b) => a + b, 0) / bandData.length;
            // Normalize to 0-1 range and amplify for better visibility
            const normalized = (average / 255) * 1.5; // Amplify by 1.5x
            newLevels.push(Math.min(normalized, 1)); // Cap at 1
          }

          setAudioLevels(newLevels);
          animationFrameRef.current = requestAnimationFrame(updateLevels);
        };

        updateLevels();
      } catch (error) {
        console.error("Failed to setup audio analysis:", error);
      }
    };

    setupAudioAnalysis();

    // Cleanup on unmount or when active changes
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch((err) => {
          console.error("[VoiceWaveform] Error closing audio context on unmount:", err);
        });
      }
      // Only stop the stream if we created it ourselves
      if (streamRef.current && !localStream) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
    };
  }, [active, localStream, barCount]);

  // Show status message during initialization
  if (
    status === "initializing" ||
    status === "reconnecting" ||
    status === "disconnected" ||
    status === "error"
  ) {
    const systemStatus = getVoiceSystemStatus(voiceSystemState);
    return (
      <div className={styles.waveformContainer}>
        <div className={styles.statusContainer}>
          {systemStatus.type === "connecting" && <div className={styles.spinner}></div>}
          <Text as="span" size="small" className={styles.statusText}>
            {systemStatus.message}
          </Text>
        </div>
      </div>
    );
  }

  if (status === "processing" || status === "speaking") {
    return (
      <div className={styles.waveformContainer}>
        <div className={styles.statusContainer}>
          {status === "processing" && <div className={styles.spinner}></div>}
          <Text as="span" size="small" className={styles.statusText}>
            {status === "speaking" ? "Speaking..." : "Thinking..."}
          </Text>
        </div>
      </div>
    );
  }

  // Show waveform only while the user-facing state is listening/connected.
  return (
    <div className={styles.waveformContainer}>
      <div className={`${styles.waveform} ${active ? styles.active : ""}`}>
        {audioLevels.map((level, index) => (
          <div
            key={index}
            className={styles.bar}
            style={{
              height: active ? `${Math.max(0.5, level * 2.5)}rem` : "0.5rem",
              transition: "height 0.08s ease-out",
            }}
          ></div>
        ))}
      </div>
      <Text as="span" size="xs" className={styles.listeningText}>
        {active ? "Listening..." : "Connecting..."}
      </Text>
    </div>
  );
};

export default VoiceWaveform;
