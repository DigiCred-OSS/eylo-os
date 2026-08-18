import { useEffect, useRef } from "preact/hooks";

interface AudioOutputProps {
  stream: MediaStream | null;
}

const AudioOutput = ({ stream }: AudioOutputProps) => {
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (audioRef.current && stream) {
      audioRef.current.srcObject = stream;
    } else if (audioRef.current) {
      audioRef.current.srcObject = null;
    }
  }, [stream]);

  return <audio ref={audioRef} autoPlay />;
};

export default AudioOutput;
