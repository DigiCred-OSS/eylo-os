const n=`/**
 * Audio worklet processor that resamples audio from 16kHz to 44.1kHz
 * 
 * This processor is essential for WebRTC audio streaming because:
 * 1. WebRTC typically receives audio at 16kHz sample rate
 * 2. Browser audio context usually expects 44.1kHz for playback
 * 3. Without resampling, audio would sound distorted or play at wrong speed
 * 
 * Uses LibSampleRate library for high-quality audio resampling.
 */
class ResampleProcessor extends AudioWorkletProcessor {
  src = null; // LibSampleRate resampler instance

  constructor(options) {
    super(options);
    this.frameCount = 0;
    this.lastLogTime = 0;
    this.init();
  }

  async init() {
    /**
     * Initialize the LibSampleRate resampler
     * 
     * Note: AudioWorklet environment doesn't have setTimeout, so we use
     * MessageChannel for creating delays while waiting for LibSampleRate to load
     */
    let retries = 0;
    while (!globalThis.LibSampleRate && retries < 50) {
      // AudioWorklet-compatible delay using MessageChannel
      await new Promise(resolve => {
        const channel = new MessageChannel();
        channel.port1.onmessage = () => resolve();
        channel.port2.postMessage(null);
      });
      retries++;
    }
    
    if (!globalThis.LibSampleRate) {
      console.error('LibSampleRate failed to load after retries');
      return;
    }
    
    const { create, ConverterType } = globalThis.LibSampleRate;

    // Configure resampler: 16kHz mono input → 44.1kHz mono output
    const nChannels = 1;
    const inputSampleRate = 16000;  // WebRTC audio sample rate
    const outputSampleRate = 44100; // Browser audio context sample rate

    create(nChannels, inputSampleRate, outputSampleRate, {
      converterType: ConverterType.SRC_SINC_BEST_QUALITY, // High quality resampling
    }).then((src) => {
      this.src = src;
    });
  }

  process(inputs, outputs, parameters) {
    /**
     * Main processing function called by Web Audio API for each audio block
     * 
     * Resamples incoming 16kHz audio to 44.1kHz for browser playback.
     * Falls back to direct copy if resampler is not ready or fails.
     */
    
    // Validate inputs and outputs
    if (!inputs[0] || !inputs[0][0] || !outputs[0] || !outputs[0][0]) {
      return true;
    }

    const inputChannel = inputs[0][0];
    const outputChannel = outputs[0][0];

    if (this.src != null) {
      try {
        // Perform high-quality resampling using LibSampleRate
        const resampled = this.src.full(inputChannel);
        
        if (resampled && resampled.length > 0) {
          // Copy resampled audio to output buffer
          const copyLength = Math.min(resampled.length, outputChannel.length);
          for (let i = 0; i < copyLength; i++) {
            outputChannel[i] = resampled[i];
          }
          
          // Zero-pad if resampled data is shorter than output buffer
          for (let i = copyLength; i < outputChannel.length; i++) {
            outputChannel[i] = 0;
          }
        } else {
          // Resampling returned no data - use fallback
          this.copyInputToOutput(inputs, outputs);
        }
      } catch (error) {
        console.error('Resampling error:', error);
        // Fallback to direct copy on error
        this.copyInputToOutput(inputs, outputs);
      }
    } else {
      // LibSampleRate not initialized yet - use direct copy as fallback
      this.copyInputToOutput(inputs, outputs);
    }

    return true; // Keep processor alive
  }

  /**
   * Fallback method: copy input directly to output without resampling
   * 
   * Used when LibSampleRate is not available or resampling fails.
   * Audio may sound distorted due to sample rate mismatch, but this
   * prevents silence and allows basic functionality.
   */
  copyInputToOutput(inputs, outputs) {
    for (let inputNum = 0; inputNum < inputs.length; inputNum++) {
      let input = inputs[inputNum];
      if (!input || !outputs[inputNum]) continue;
      
      for (let channelNum = 0; channelNum < input.length; channelNum++) {
        let channel = input[channelNum];
        if (!channel || !outputs[inputNum][channelNum]) continue;
        
        const outputChannel = outputs[inputNum][channelNum];
        const copyLength = Math.min(channel.length, outputChannel.length);
        
        // Direct sample-by-sample copy
        for (let sampleNum = 0; sampleNum < copyLength; sampleNum++) {
          outputChannel[sampleNum] = channel[sampleNum];
        }
      }
    }
  }
}

registerProcessor('resample-processor', ResampleProcessor);`;export{n as default};
