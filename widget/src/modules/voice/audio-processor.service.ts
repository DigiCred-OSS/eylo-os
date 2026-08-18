import { logger } from "@eylo/utils";
import type { AudioProcessorConfig } from "./types";

export class AudioProcessor {
  private static _instance: AudioProcessor | null = null;
  inputContext: AudioContext | null = null;
  outputContext: AudioContext | null = null;
  private outputAudioElement: HTMLAudioElement | null = null;
  private config!: AudioProcessorConfig;
  isDownsamplingEnabled: boolean = false;
  isUpsamplingEnabled: boolean = false;
  outputWorkletNode: AudioWorkletNode | null = null;
  inputSource: MediaStreamAudioSourceNode | null = null;
  public onPcmData: ((data: ArrayBuffer) => void) | null = null;

  constructor(config: AudioProcessorConfig) {
    if (AudioProcessor._instance) {
      return AudioProcessor._instance;
    }
    this.config = config;
    AudioProcessor._instance = this;
  }

  async initialize(): Promise<boolean> {
    // Create separate contexts for input and output
    this.inputContext = new window.AudioContext({
      // sampleRate: this.config.sampleRate,
      sampleRate: 44100,
      latencyHint: "interactive",
    });
    logger.debug(
      `[AudioProcessor] Input context created. State: ${this.inputContext.state}, Sample Rate: ${this.inputContext.sampleRate}`
    );

    this.outputContext = new window.AudioContext({
      // sampleRate: this.config.sampleRate,
      sampleRate: 44100,
      latencyHint: "interactive",
    });
    logger.debug(
      `[AudioProcessor] Output context created. State: ${this.outputContext.state}, Sample Rate: ${this.outputContext.sampleRate}`
    );

    // Resume contexts if they are in a suspended state, which is common
    // in browsers due to auto-play policies.
    if (this.inputContext.state === "suspended") {
      logger.debug("[AudioProcessor] Input context is suspended, resuming...");
      await this.inputContext.resume();
      logger.debug(`[AudioProcessor] Input context resumed. New state: ${this.inputContext.state}`);
    }
    if (this.outputContext.state === "suspended") {
      logger.debug("[AudioProcessor] Output context is suspended, resuming...");
      await this.outputContext.resume();
      logger.debug(
        `[AudioProcessor] Output context resumed. New state: ${this.outputContext.state}`
      );
    }

    // Load resampling worklets
    // await this.loadResamplingWorklets();

    // initialize input downsampling worklet
    await this.initializeDownsamplingWorklet();
    // Initialize output upsampling worklet
    await this.initializeUpsamplingWorklet();

    return true;
  }

  private async initializeDownsamplingWorklet() {
    if (!this.inputContext) return;

    // Always re-register worklet for each new AudioContext instance
    try {
      // Import the worklet script as a raw string
      const workletCode = (await import("./audio-processor.worklet.js?raw")).default;

      // Create a Blob from the string
      const blob = new Blob([workletCode], { type: "application/javascript" });
      const workletUrl = URL.createObjectURL(blob);

      // Load the worklet from the Blob URL
      await this.inputContext.audioWorklet.addModule(workletUrl);

      // Clean up the object URL
      URL.revokeObjectURL(workletUrl);

      this.isDownsamplingEnabled = true;
      logger.debug("[AudioProcessor] STT down-sampling worklet registered successfully");
    } catch (e) {
      logger.error(`[AudioProcessor] Downsampling worklet failed: ${e}`);
      this.isDownsamplingEnabled = false;
    }
  }

  // Initialize upsampling worklet for TTS audio (16kHz → 48kHz)
  private async initializeUpsamplingWorklet() {
    if (!this.outputContext) return;

    // Always re-register worklet for each new AudioContext instance
    try {
      // Load LibSampleRate first, then our resampler that depends on it
      await this.outputContext.audioWorklet.addModule(
        "https://cdn.jsdelivr.net/npm/@alexanderolsen/libsamplerate-js/dist/libsamplerate.worklet.js"
      );

      // Import the worklet script as a raw string
      const workletCode = (await import("./resampler-v0.worklet.js?raw")).default;

      // Create a Blob from the string
      const blob = new Blob([workletCode], { type: "application/javascript" });
      const workletUrl = URL.createObjectURL(blob);

      // Load the worklet from the Blob URL
      await this.outputContext.audioWorklet.addModule(workletUrl);

      // Clean up the object URL
      URL.revokeObjectURL(workletUrl);

      this.isUpsamplingEnabled = true;
      logger.debug("[AudioProcessor] TTS upsampling worklet registered successfully");
    } catch (error) {
      logger.error(`[AudioProcessor] Upsampling worklet failed: ${error}`);
      this.isUpsamplingEnabled = false;
    }
  }

  /**
   * Returns the effective input sample rate.
   * Falls back to configured sample rate if the input AudioContext is not initialized yet.
   */
  public getInputSampleRate(): number {
    return this.inputContext?.sampleRate ?? this.config.sampleRate;
  }

  /**
   * Returns the effective output sample rate.
   * Falls back to configured sample rate if the output AudioContext is not initialized yet.
   */
  public getOutputSampleRate(): number {
    return this.outputContext?.sampleRate ?? this.config.sampleRate;
  }

  setupInputProcessing(stream: MediaStream): void {
    if (!this.inputContext || !stream) {
      logger.error(
        "[AudioProcessor] Cannot setup input processing without input context or stream."
      );
      return;
    }

    try {
      logger.debug("[AudioProcessor] Setting up input processing...");

      // Ensure context is running
      if (this.inputContext.state === "suspended") {
        this.inputContext.resume().then(() => {
          logger.debug("[AudioProcessor] Input context resumed in setupInputProcessing");
        });
      }

      this.inputSource = this.inputContext.createMediaStreamSource(stream);
      logger.debug("[AudioProcessor] Created MediaStreamSource from input stream.");
    } catch (error) {
      logger.error(`Input setup failed: ${error}`);
    }
  }

  /**
   * CRITICAL: Stop all tracks from the MediaStreamSource's internal stream
   * The MediaStreamAudioSourceNode holds a reference to the stream, which keeps
   * tracks alive even after we think we've stopped them elsewhere
   */
  stopInputTracks(): void {
    if (this.inputSource) {
      try {
        // Access the MediaStream from the source node and stop all its tracks
        const stream = (this.inputSource as any).mediaStream;
        if (stream && stream.getTracks) {
          const tracks = stream.getTracks();
          logger.debug(`[AudioProcessor] Stopping ${tracks.length} tracks from MediaStreamSource`);
          tracks.forEach((track: MediaStreamTrack) => {
            logger.debug(
              `[AudioProcessor] Stopping source track: ${track.kind}, readyState: ${track.readyState}, id: ${track.id}`
            );
            track.stop();
            logger.debug(
              `[AudioProcessor] Source track after stop: readyState: ${track.readyState}`
            );
          });
        }
      } catch (err) {
        logger.error("[AudioProcessor] Error stopping input source tracks:", err);
      }
    }
  }

  setupOutputProcessing(stream: MediaStream): void {
    if (!this.outputContext || !stream) {
      logger.error("Output context or stream not initialized");
      return;
    }

    try {
      // Ensure context is running
      if (this.outputContext.state === "suspended") {
        this.outputContext.resume().then(() => {
          logger.debug("Output context resumed in setupOutputProcessing");
        });
      }

      // Create audio element for the remote stream
      if (!this.outputAudioElement) {
        this.outputAudioElement = document.createElement("audio");
        this.outputAudioElement.srcObject = stream;
        this.outputAudioElement.autoplay = true;
        // @ts-ignore - playsInline is valid on HTMLMediaElement at runtime
        // this.outputAudioElement.playsInline = true;
        this.outputAudioElement.volume = 1.0;
        document.body.appendChild(this.outputAudioElement);
      }

      // Wait for audio element to be ready
      this.outputAudioElement.onloadedmetadata = () => {
        logger.debug("Output audio element metadata loaded");
      };

      const outputSource = this.outputContext.createMediaElementSource(this.outputAudioElement);

      // Only create AudioWorkletNode if upsampling is enabled
      if (this.isUpsamplingEnabled) {
        try {
          this.outputWorkletNode = new AudioWorkletNode(this.outputContext, "resample-processor");
          outputSource.connect(this.outputWorkletNode);
          this.outputWorkletNode.connect(this.outputContext.destination);
          logger.debug("[AudioProcessor] Output worklet connected with upsampling");
        } catch (error) {
          logger.error(`[AudioProcessor] Failed to create AudioWorkletNode: ${error}`);
          // Fallback: connect directly to destination without upsampling
          outputSource.connect(this.outputContext.destination);
          logger.debug("[AudioProcessor] Output connected directly (worklet failed)");
        }
      } else {
        // Connect directly to destination if upsampling is not available
        outputSource.connect(this.outputContext.destination);
        logger.debug("[AudioProcessor] Output connected directly (no upsampling)");
      }

      this.outputAudioElement
        .play()
        .then(() => {
          logger.debug("Output audio playback started");
        })
        .catch((err) => {
          logger.error(`Audio playback failed: ${err.message}`);
          // Try to resume on user interaction
          document.addEventListener(
            "click",
            () => {
              this.outputAudioElement?.play().catch(() => {});
            },
            { once: true }
          );
        });
    } catch (error) {
      logger.error(`Output setup failed: ${error}`);
    }
  }

  async cleanup(): Promise<void> {
    logger.debug("[AudioProcessor] Starting cleanup...");

    // STEP 0: CRITICAL - Stop tracks held by MediaStreamSource FIRST
    // MediaStreamAudioSourceNode holds a reference to the MediaStream which keeps tracks alive
    this.stopInputTracks();

    // STEP 1: Disconnect all audio nodes (while contexts are still open)
    if (this.inputSource) {
      try {
        this.inputSource.disconnect();
        logger.debug("[AudioProcessor] Input source disconnected");
      } catch (err) {
        logger.error("[AudioProcessor] Error disconnecting input source:", err);
      }
      this.inputSource = null;
    }

    if (this.outputWorkletNode) {
      try {
        this.outputWorkletNode.disconnect();
        logger.debug("[AudioProcessor] Output worklet disconnected");
      } catch (err) {
        logger.error("[AudioProcessor] Error disconnecting output worklet:", err);
      }
      this.outputWorkletNode = null;
    }

    // STEP 2: Clear output audio element
    if (this.outputAudioElement) {
      this.outputAudioElement.pause();
      this.outputAudioElement.srcObject = null;
      if (this.outputAudioElement.parentNode) {
        this.outputAudioElement.parentNode.removeChild(this.outputAudioElement);
      }
      this.outputAudioElement = null;
      logger.debug("[AudioProcessor] Output audio element cleared");
    }

    // STEP 3: Close audio contexts to release audio device access
    // CRITICAL: We must AWAIT these to ensure contexts are fully closed before proceeding
    const closePromises: Promise<void>[] = [];

    if (this.inputContext && this.inputContext.state !== "closed") {
      const closePromise = this.inputContext
        .close()
        .then(() => {
          logger.debug("[AudioProcessor] Input context closed successfully");
        })
        .catch((err) => {
          logger.error("[AudioProcessor] Error closing input context:", err);
        });
      closePromises.push(closePromise);
      this.inputContext = null;
    }

    if (this.outputContext && this.outputContext.state !== "closed") {
      const closePromise = this.outputContext
        .close()
        .then(() => {
          logger.debug("[AudioProcessor] Output context closed successfully");
        })
        .catch((err) => {
          logger.error("[AudioProcessor] Error closing output context:", err);
        });
      closePromises.push(closePromise);
      this.outputContext = null;
    }

    // Wait for all contexts to close
    await Promise.all(closePromises);

    logger.debug("[AudioProcessor] Cleanup complete");
  }
}
