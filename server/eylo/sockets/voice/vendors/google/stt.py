"""Google Cloud Speech STT - gRPC streaming speech recognition.

Google Cloud Speech-to-Text provides enterprise-grade speech recognition
with support for 125+ languages. This implementation uses gRPC streaming
for real-time transcription.

Based on: livekit-plugins-google/livekit/plugins/google/stt.py
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Literal

from google.cloud import speech_v1 as speech
from google.oauth2 import service_account

from eylo.sockets.voice.audio import AudioFrame

# Google Speech models
GoogleModels = Literal[
    "latest_long",  # Latest long-form model (recommended for most use cases)
    "latest_short",  # Latest short-form model (optimized for commands)
    "command_and_search",  # Optimized for short queries
    "phone_call",  # Optimized for phone/video calls
    "video",  # Optimized for video
    "default",  # Default model
]

# Google Speech languages (subset of most common - full list has 125+)
GoogleLanguages = Literal[
    "en-US",  # English (US)
    "en-GB",  # English (UK)
    "en-AU",  # English (Australia)
    "en-CA",  # English (Canada)
    "en-IN",  # English (India)
    "es-ES",  # Spanish (Spain)
    "es-MX",  # Spanish (Mexico)
    "es-US",  # Spanish (US)
    "fr-FR",  # French (France)
    "fr-CA",  # French (Canada)
    "de-DE",  # German (Germany)
    "it-IT",  # Italian (Italy)
    "pt-BR",  # Portuguese (Brazil)
    "pt-PT",  # Portuguese (Portugal)
    "zh-CN",  # Chinese (Simplified, China)
    "zh-TW",  # Chinese (Traditional, Taiwan)
    "ja-JP",  # Japanese (Japan)
    "ko-KR",  # Korean (Korea)
    "hi-IN",  # Hindi (India)
    "nl-NL",  # Dutch (Netherlands)
    "ru-RU",  # Russian (Russia)
    "ar-SA",  # Arabic (Saudi Arabia)
    "tr-TR",  # Turkish (Turkey)
    "pl-PL",  # Polish (Poland)
    "sv-SE",  # Swedish (Sweden)
    "da-DK",  # Danish (Denmark)
    "fi-FI",  # Finnish (Finland)
    "no-NO",  # Norwegian (Norway)
    "cs-CZ",  # Czech (Czech Republic)
    "el-GR",  # Greek (Greece)
    "he-IL",  # Hebrew (Israel)
    "id-ID",  # Indonesian (Indonesia)
    "ms-MY",  # Malay (Malaysia)
    "th-TH",  # Thai (Thailand)
    "vi-VN",  # Vietnamese (Vietnam)
    "uk-UA",  # Ukrainian (Ukraine)
    "ro-RO",  # Romanian (Romania)
    "hu-HU",  # Hungarian (Hungary)
    "bg-BG",  # Bulgarian (Bulgaria)
]

SAMPLE_RATE = 16000


@dataclass
class STTOptions:
    """Google Cloud Speech STT configuration."""

    language: str
    model: str
    interim_results: bool
    punctuation: bool
    profanity_filter: bool
    sample_rate: int
    detect_language: bool
    alternative_languages: list[str]


class GoogleSTT:
    """Google Cloud Speech STT using streaming recognition via gRPC."""

    def __init__(
        self,
        *,
        language: GoogleLanguages | str = "en-US",
        model: GoogleModels | str = "latest_long",
        interim_results: bool = True,
        punctuation: bool = True,
        profanity_filter: bool = False,
        sample_rate: int = SAMPLE_RATE,
        service_account_json: str,
        detect_language: bool = False,
        alternative_languages: list[str] | None = None,
    ) -> None:
        if not service_account_json:
            raise ValueError("Google service_account_json is required.")
        try:
            service_account_info = json.loads(service_account_json)
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info
            )
        except (TypeError, ValueError):
            raise ValueError("Google service_account_json is invalid.") from None
        self._client = speech.SpeechClient(credentials=credentials)
        self._opts = STTOptions(
            language=language,
            model=model,
            interim_results=interim_results,
            punctuation=punctuation,
            profanity_filter=profanity_filter,
            sample_rate=sample_rate,
            detect_language=detect_language,
            alternative_languages=alternative_languages or [],
        )

    @property
    def language(self) -> str:
        """Get the language being used."""
        return self._opts.language

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return "Google Cloud Speech"

    @property
    def sample_rate(self) -> int:
        """Get the audio sample rate."""
        return self._opts.sample_rate

    def stream(self) -> GoogleSTTStream:
        """Create a streaming STT session."""
        return GoogleSTTStream(
            opts=self._opts,
            client=self._client,
        )

    def close(self) -> None:
        """Close the gRPC client."""
        if self._client:
            self._client.transport.grpc_channel.close()


class GoogleSTTStream:
    """Google Cloud Speech gRPC streaming STT session.

    Manages gRPC bi-directional streaming to Google Cloud Speech for
    real-time transcription. Automatically handles reconnection and
    audio chunking.

    Protocol:
        1. Open bi-directional gRPC stream
        2. Send StreamingRecognitionConfig in first request
        3. Send audio chunks in subsequent requests
        4. Receive StreamingRecognitionResponse messages
        5. Close stream when done

    Response Types:
        - Interim results: is_final=False
        - Final results: is_final=True with confidence scores
        - End of utterance: speech_event_type=END_OF_SINGLE_UTTERANCE
    """

    def __init__(
        self,
        *,
        opts: STTOptions,
        client: speech.SpeechClient,
    ) -> None:
        self._opts = opts
        self._client = client
        self._closed = False

        # Audio input queue
        self._input_queue: asyncio.Queue[AudioFrame | None] = asyncio.Queue()

        # Transcription output queue
        self._output_queue: asyncio.Queue[dict | None] = asyncio.Queue()

        # Start background task
        self._task = asyncio.create_task(self._run())

    async def push_audio(self, frame: AudioFrame) -> None:
        """Push audio frame for transcription.

        Args:
            frame: AudioFrame to transcribe.

        """
        if not self._closed:
            await self._input_queue.put(frame)

    async def flush(self) -> None:
        """Flush any pending audio and get final transcription."""
        if not self._closed:
            await self._input_queue.put(None)  # Sentinel for flush

    def __aiter__(self):
        """Async iterator for transcription events."""
        return self

    async def __anext__(self) -> dict:
        """Get next transcription event.

        Returns:
            dict with transcription data.

        Raises:
            StopAsyncIteration when stream is closed.

        """
        event = await self._output_queue.get()
        if event is None:
            raise StopAsyncIteration
        return event

    def _build_config(self) -> speech.StreamingRecognitionConfig:
        """Build streaming recognition configuration."""
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self._opts.sample_rate,
            language_code=self._opts.language,
            model=self._opts.model,
            enable_automatic_punctuation=self._opts.punctuation,
            profanity_filter=self._opts.profanity_filter,
        )

        # Add language detection if enabled
        if self._opts.detect_language:
            config.alternative_language_codes.extend(self._opts.alternative_languages)

        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=self._opts.interim_results,
        )

        return streaming_config

    async def _run(self) -> None:
        """Main gRPC streaming task loop."""
        try:
            while not self._closed:
                try:
                    await self._run_stream()
                except Exception:
                    if self._closed:
                        break
                    # Log error and reconnect
                    await asyncio.sleep(1)
        finally:
            await self._output_queue.put(None)

    async def _request_generator(self):
        """Generate requests for gRPC streaming."""
        # First request contains configuration
        config = self._build_config()
        yield speech.StreamingRecognizeRequest(streaming_config=config)

        # Subsequent requests contain audio data
        while not self._closed:
            frame = await self._input_queue.get()

            if frame is None:
                # Flush signal - stop sending audio
                break

            # Send audio chunk
            # frame.data is already bytes for Google
            yield speech.StreamingRecognizeRequest(audio_content=frame.data)

    async def _run_stream(self) -> None:
        """Run gRPC streaming recognition."""
        # Start bi-directional streaming
        requests = self._request_generator()
        responses = self._client.streaming_recognize(requests)

        # Process responses
        for response in responses:
            if self._closed:
                break

            # Process results
            for result in response.results:
                # Convert to dict format compatible with our interface
                event = {
                    "is_final": result.is_final,
                    "stability": result.stability,
                    "alternatives": [
                        {
                            "transcript": alt.transcript,
                            "confidence": alt.confidence,
                        }
                        for alt in result.alternatives
                    ],
                }

                # Add language code if available
                if result.language_code:
                    event["language_code"] = result.language_code

                await self._output_queue.put(event)

    async def aclose(self) -> None:
        """Close the stream."""
        if self._closed:
            return

        self._closed = True
        await self._input_queue.put(None)  # Wake up request generator

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
