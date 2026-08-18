export const AUDIO_CONSTRAINTS: MediaStreamConstraints = {
  audio: {
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
    sampleRate: 44100,
    sampleSize: 16,
  },
  video: false,
};

export const AUDIO_PROCESSOR_CONFIG = {
  sampleRate: 16000, // Match server expectation for STT
  channelCount: 1,
  enableResampling: true,
};
