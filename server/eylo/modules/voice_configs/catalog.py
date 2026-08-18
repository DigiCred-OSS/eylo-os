"""Voice providers and their operator-facing configuration choices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from eylo.common.contracts.aws_catalog import AWS_REGION_OPTIONS

__all__ = [
    "AMAZON_NOVA_SONIC_ENDPOINTING_SENSITIVITIES",
    "AMAZON_NOVA_SONIC_MODELS",
    "AMAZON_NOVA_SONIC_VOICES",
    "RealtimeProviders",
    "STTProviders",
    "TTSProviders",
    "VoiceConfigFieldCatalog",
    "VoiceConfigOption",
    "VoiceKind",
    "voice_config_field_catalog",
]

AMAZON_NOVA_SONIC_MODELS = ("amazon.nova-2-sonic-v1:0",)
AMAZON_NOVA_SONIC_VOICES = (
    "matthew",
    "tiffany",
    "amy",
    "olivia",
    "lupe",
    "carlos",
    "ambre",
    "florian",
    "lennart",
    "beatrice",
    "lorenzo",
    "tina",
    "carolina",
    "leo",
    "kiara",
    "arjun",
)
AMAZON_NOVA_SONIC_ENDPOINTING_SENSITIVITIES = ("HIGH", "MEDIUM", "LOW")


class VoiceKind(str, Enum):
    STT = "stt"
    TTS = "tts"
    REALTIME = "realtime"


class RealtimeProviders(str, Enum):
    AMAZON_NOVA_SONIC = "amazon-nova-sonic"
    GEMINI_LIVE = "gemini-live"
    OPENAI_REALTIME = "openai-realtime"


class STTProviders(str, Enum):
    AMAZON_TRANSCRIBE = "amazon-transcribe"
    DEEPGRAM = "deepgram"
    DEEPGRAM_FLUX = "deepgram-flux"
    SARVAM = "sarvam"
    ASSEMBLYAI = "assemblyai"
    CARTESIA = "cartesia"
    GOOGLE = "google"
    GLADIA = "gladia"
    REVAI = "revai"
    SPEECHMATICS = "speechmatics"


class TTSProviders(str, Enum):
    AMAZON_POLLY = "amazon-polly"
    ELEVENLABS = "elevenlabs"
    CARTESIA = "cartesia"
    SARVAM = "sarvam"
    OPENAI = "openai"
    DEEPGRAM = "deepgram"
    GROQ = "groq"
    RIME = "rime"
    SMALLEST = "smallest"
    HUME = "hume"
    MURF = "murf"


@dataclass(frozen=True)
class VoiceConfigOption:
    """One value an operator can choose without consulting vendor docs."""

    value: str
    label: str


@dataclass(frozen=True)
class VoiceConfigFieldCatalog:
    """Published choices for one provider config field.

    ``allow_custom`` is reserved for vendor-owned catalogs such as cloned voices.
    The published choices cover common built-in values; the escape hatch keeps
    account-specific IDs usable without pretending Eylo owns that catalog.
    """

    options: tuple[VoiceConfigOption, ...]
    allow_custom: bool = False


def _option(value: str, label: str | None = None) -> VoiceConfigOption:
    return VoiceConfigOption(value=value, label=label or value)


def _options(*values: str) -> tuple[VoiceConfigOption, ...]:
    return tuple(_option(value) for value in values)


def _named_option(value: str, label: str) -> VoiceConfigOption:
    if label.partition(" · ")[0].casefold() == value.casefold():
        return _option(value, label)
    return _option(value, f"{label} · {value}")


def _named_options(
    *values: tuple[str, str],
) -> tuple[VoiceConfigOption, ...]:
    return tuple(_named_option(value, label) for value, label in values)


_AWS_REGIONS = tuple(_option(value, label) for value, label in AWS_REGION_OPTIONS)

_ISO_LANGUAGES = _named_options(
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("hi", "Hindi"),
    ("pt", "Portuguese"),
    ("it", "Italian"),
    ("nl", "Dutch"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("zh", "Chinese"),
    ("ar", "Arabic"),
    ("bn", "Bengali"),
    ("gu", "Gujarati"),
    ("kn", "Kannada"),
    ("ml", "Malayalam"),
    ("mr", "Marathi"),
    ("pa", "Punjabi"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
    ("ru", "Russian"),
    ("tr", "Turkish"),
    ("uk", "Ukrainian"),
    ("vi", "Vietnamese"),
    ("id", "Indonesian"),
    ("pl", "Polish"),
    ("sv", "Swedish"),
    ("da", "Danish"),
    ("fi", "Finnish"),
    ("no", "Norwegian"),
    ("cs", "Czech"),
    ("el", "Greek"),
    ("he", "Hebrew"),
    ("ro", "Romanian"),
    ("hu", "Hungarian"),
    ("th", "Thai"),
    ("ur", "Urdu"),
)

_COMMON_LOCALES = _named_options(
    ("en-US", "English (US)"),
    ("en-GB", "English (UK)"),
    ("en-IN", "English (India)"),
    ("en-AU", "English (Australia)"),
    ("en-CA", "English (Canada)"),
    ("es-ES", "Spanish (Spain)"),
    ("es-MX", "Spanish (Mexico)"),
    ("es-US", "Spanish (US)"),
    ("fr-FR", "French (France)"),
    ("fr-CA", "French (Canada)"),
    ("de-DE", "German"),
    ("it-IT", "Italian"),
    ("pt-BR", "Portuguese (Brazil)"),
    ("pt-PT", "Portuguese (Portugal)"),
    ("hi-IN", "Hindi"),
    ("bn-IN", "Bengali"),
    ("gu-IN", "Gujarati"),
    ("kn-IN", "Kannada"),
    ("ml-IN", "Malayalam"),
    ("mr-IN", "Marathi"),
    ("pa-IN", "Punjabi"),
    ("ta-IN", "Tamil"),
    ("te-IN", "Telugu"),
    ("ar-SA", "Arabic (Saudi Arabia)"),
    ("ar-AE", "Arabic (Gulf)"),
    ("ja-JP", "Japanese"),
    ("ko-KR", "Korean"),
    ("zh-CN", "Chinese (Simplified)"),
    ("zh-TW", "Chinese (Traditional)"),
    ("nl-NL", "Dutch"),
    ("ru-RU", "Russian"),
    ("tr-TR", "Turkish"),
)

_SARVAM_LANGUAGES = _named_options(
    ("en-IN", "English (India)"),
    ("hi-IN", "Hindi"),
    ("bn-IN", "Bengali"),
    ("ta-IN", "Tamil"),
    ("te-IN", "Telugu"),
    ("gu-IN", "Gujarati"),
    ("kn-IN", "Kannada"),
    ("ml-IN", "Malayalam"),
    ("mr-IN", "Marathi"),
    ("pa-IN", "Punjabi"),
    ("od-IN", "Odia"),
)

_SARVAM_VOICES = _options(
    "shubh",
    "aditya",
    "ritu",
    "priya",
    "neha",
    "rahul",
    "pooja",
    "rohan",
    "simran",
    "kavya",
    "amit",
    "dev",
    "ishita",
    "shreya",
    "ratan",
    "varun",
    "manan",
    "sumit",
    "roopa",
    "kabir",
    "aayan",
    "ashutosh",
    "advait",
    "anand",
    "tanya",
    "tarun",
    "sunny",
    "mani",
    "gokul",
    "vijay",
    "shruti",
    "suhani",
    "mohit",
    "kavitha",
    "rehan",
    "soham",
    "rupali",
)

_OPENAI_VOICES = _options(
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "fable",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
)

_GEMINI_VOICES = _named_options(
    ("Zephyr", "Bright"),
    ("Puck", "Upbeat"),
    ("Charon", "Informative"),
    ("Kore", "Firm"),
    ("Fenrir", "Excitable"),
    ("Leda", "Youthful"),
    ("Orus", "Firm"),
    ("Aoede", "Breezy"),
    ("Callirrhoe", "Easy-going"),
    ("Autonoe", "Bright"),
    ("Enceladus", "Breathy"),
    ("Iapetus", "Clear"),
    ("Umbriel", "Easy-going"),
    ("Algieba", "Smooth"),
    ("Despina", "Smooth"),
    ("Erinome", "Clear"),
    ("Algenib", "Gravelly"),
    ("Rasalgethi", "Informative"),
    ("Laomedeia", "Upbeat"),
    ("Achernar", "Soft"),
    ("Alnilam", "Firm"),
    ("Schedar", "Even"),
    ("Gacrux", "Mature"),
    ("Pulcherrima", "Forward"),
    ("Achird", "Friendly"),
    ("Zubenelgenubi", "Casual"),
    ("Vindemiatrix", "Gentle"),
    ("Sadachbia", "Lively"),
    ("Sadaltager", "Knowledgeable"),
    ("Sulafat", "Warm"),
)

_POLLY_LANGUAGES = _named_options(
    ("arb", "Arabic"),
    ("ar-AE", "Arabic (Gulf)"),
    ("ca-ES", "Catalan"),
    ("cmn-CN", "Chinese (Mandarin)"),
    ("yue-CN", "Chinese (Cantonese)"),
    ("cs-CZ", "Czech"),
    ("da-DK", "Danish"),
    ("nl-NL", "Dutch"),
    ("nl-BE", "Dutch (Belgian)"),
    ("en-AU", "English (Australia)"),
    ("en-GB", "English (UK)"),
    ("en-IN", "English (India)"),
    ("en-IE", "English (Ireland)"),
    ("en-NZ", "English (New Zealand)"),
    ("en-SG", "English (Singapore)"),
    ("en-ZA", "English (South Africa)"),
    ("en-US", "English (US)"),
    ("en-GB-WLS", "English (Welsh)"),
    ("fi-FI", "Finnish"),
    ("fr-FR", "French"),
    ("fr-BE", "French (Belgian)"),
    ("fr-CA", "French (Canadian)"),
    ("de-DE", "German"),
    ("de-AT", "German (Austrian)"),
    ("de-CH", "German (Swiss)"),
    ("hi-IN", "Hindi"),
    ("is-IS", "Icelandic"),
    ("it-IT", "Italian"),
    ("ja-JP", "Japanese"),
    ("ko-KR", "Korean"),
    ("nb-NO", "Norwegian"),
    ("pl-PL", "Polish"),
    ("pt-BR", "Portuguese (Brazil)"),
    ("pt-PT", "Portuguese (Portugal)"),
    ("ro-RO", "Romanian"),
    ("ru-RU", "Russian"),
    ("es-ES", "Spanish (Spain)"),
    ("es-MX", "Spanish (Mexico)"),
    ("es-US", "Spanish (US)"),
    ("sv-SE", "Swedish"),
)

_POLLY_VOICES = _named_options(
    ("Aditi", "Aditi · English (India), Hindi"),
    ("Amy", "Amy · English (UK)"),
    ("Aria", "Aria · English (New Zealand)"),
    ("Arthur", "Arthur · English (UK)"),
    ("Ayanda", "Ayanda · English (South Africa)"),
    ("Brian", "Brian · English (UK)"),
    ("Danielle", "Danielle · English (US)"),
    ("Emma", "Emma · English (UK)"),
    ("Gregory", "Gregory · English (US)"),
    ("Ivy", "Ivy · English (US)"),
    ("Jasmine", "Jasmine · English (Singapore)"),
    ("Joanna", "Joanna · English (US)"),
    ("Joey", "Joey · English (US)"),
    ("Kajal", "Kajal · English (India), Hindi"),
    ("Kendra", "Kendra · English (US)"),
    ("Kevin", "Kevin · English (US)"),
    ("Kimberly", "Kimberly · English (US)"),
    ("Matthew", "Matthew · English (US)"),
    ("Nicole", "Nicole · English (Australia)"),
    ("Olivia", "Olivia · English (Australia)"),
    ("Patrick", "Patrick · English (US)"),
    ("Raveena", "Raveena · English (India)"),
    ("Ruth", "Ruth · English (US)"),
    ("Salli", "Salli · English (US)"),
    ("Stephen", "Stephen · English (US)"),
    ("Tiffany", "Tiffany · English (US)"),
    ("Zeina", "Zeina · Arabic"),
    ("Hala", "Hala · Arabic (Gulf)"),
    ("Zayd", "Zayd · Arabic (Gulf)"),
    ("Zhiyu", "Zhiyu · Chinese (Mandarin)"),
    ("Celine", "Celine · French"),
    ("Lea", "Lea · French"),
    ("Florian", "Florian · French"),
    ("Vicki", "Vicki · German"),
    ("Daniel", "Daniel · German"),
    ("Lennart", "Lennart · German"),
    ("Beatrice", "Beatrice · Italian"),
    ("Lorenzo", "Lorenzo · Italian"),
    ("Mizuki", "Mizuki · Japanese"),
    ("Takumi", "Takumi · Japanese"),
    ("Seoyeon", "Seoyeon · Korean"),
    ("Camila", "Camila · Portuguese (Brazil)"),
    ("Thiago", "Thiago · Portuguese (Brazil)"),
    ("Lucia", "Lucia · Spanish (Spain)"),
    ("Sergio", "Sergio · Spanish (Spain)"),
    ("Mia", "Mia · Spanish (Mexico)"),
    ("Lupe", "Lupe · Spanish (US)"),
    ("Miguel", "Miguel · Spanish (US)"),
)

_ELEVENLABS_VOICES = _named_options(
    ("JBFqnCBsd6RMkjVDRZzb", "George"),
    ("EXAVITQu4vr4xnSDxMaL", "Sarah"),
    ("CwhRBWXzGAHq8TQ4Fs17", "Roger"),
    ("FGY2WhTYpPnrIDTdsKH5", "Laura"),
    ("IKne3meq5aSn9XLyUdCD", "Charlie"),
    ("Xb7hH8MSUJpSbSDYk0k2", "Alice"),
    ("TX3LPaxmHKxFdv7VOQHJ", "Liam"),
    ("XrExE9yKIg1WjnnlVkGX", "Matilda"),
    ("cgSgspJ2msm6clMCkdW9", "Jessica"),
    ("cjVigY5qzO86Huf0OWal", "Eric"),
    ("iP95p4xoKVk53GoZ742B", "Chris"),
    ("nPczCjzI2devNBz1zQrb", "Brian"),
    ("onwK4e9ZLuTAKqWW03F9", "Daniel"),
    ("pFZP5JQG7iQjIQuC4Bku", "Lily"),
    ("pqHfZKP75CvOlQylNhV4", "Bill"),
)

_DEEPGRAM_TTS_MODELS = _named_options(
    ("aura-2-thalia-en", "Thalia · English (US)"),
    ("aura-2-andromeda-en", "Andromeda · English (US)"),
    ("aura-2-helena-en", "Helena · English (US)"),
    ("aura-2-apollo-en", "Apollo · English (US)"),
    ("aura-2-arcas-en", "Arcas · English (US)"),
    ("aura-2-aries-en", "Aries · English (US)"),
    ("aura-2-draco-en", "Draco · English (UK)"),
    ("aura-2-hyperion-en", "Hyperion · English (Australia)"),
    ("aura-2-celeste-es", "Celeste · Spanish (Colombia)"),
    ("aura-2-nestor-es", "Nestor · Spanish (Spain)"),
    ("aura-2-rhea-nl", "Rhea · Dutch"),
    ("aura-2-agathe-fr", "Agathe · French"),
    ("aura-2-julius-de", "Julius · German"),
)

_VOICE_FIELD_CATALOGS: dict[
    tuple[VoiceKind, str, str], VoiceConfigFieldCatalog
] = {
    # AWS credentials can also target GovCloud/China partitions, so region keeps
    # a custom escape hatch even though common commercial regions are published.
    **{
        (kind, provider, "region"): VoiceConfigFieldCatalog(
            _AWS_REGIONS,
            allow_custom=True,
        )
        for kind, provider in (
            (VoiceKind.STT, STTProviders.AMAZON_TRANSCRIBE.value),
            (VoiceKind.TTS, TTSProviders.AMAZON_POLLY.value),
            (VoiceKind.REALTIME, RealtimeProviders.AMAZON_NOVA_SONIC.value),
        )
    },
    (VoiceKind.STT, STTProviders.AMAZON_TRANSCRIBE.value, "language"):
        VoiceConfigFieldCatalog(_COMMON_LOCALES, allow_custom=True),
    (VoiceKind.STT, STTProviders.DEEPGRAM.value, "model"):
        VoiceConfigFieldCatalog(
            _options(
                "nova-3",
                "nova-3-general",
                "nova-3-medical",
                "nova-2",
                "nova-2-general",
                "nova-2-phonecall",
                "nova-2-meeting",
                "nova-2-medical",
                "nova-2-finance",
                "nova-2-conversationalai",
            ),
            allow_custom=True,
        ),
    (VoiceKind.STT, STTProviders.DEEPGRAM.value, "language"):
        VoiceConfigFieldCatalog(_ISO_LANGUAGES, allow_custom=True),
    (VoiceKind.STT, STTProviders.DEEPGRAM_FLUX.value, "model"):
        VoiceConfigFieldCatalog(
            _named_options(
                ("flux-general-en", "Flux · English"),
                ("flux-general-multi", "Flux · Multilingual"),
            )
        ),
    (VoiceKind.STT, STTProviders.SARVAM.value, "model"):
        VoiceConfigFieldCatalog(_options("saaras:v3", "saarika:v2.5")),
    (VoiceKind.STT, STTProviders.SARVAM.value, "language"):
        VoiceConfigFieldCatalog(_SARVAM_LANGUAGES),
    (VoiceKind.STT, STTProviders.SARVAM.value, "mode"):
        VoiceConfigFieldCatalog(
            _options("transcribe", "translate", "verbatim", "translit", "codemix")
        ),
    (VoiceKind.STT, STTProviders.SARVAM.value, "input_audio_codec"):
        VoiceConfigFieldCatalog(
            _options("pcm_s16le", "pcm_l16", "pcm_raw", "wav")
        ),
    (VoiceKind.STT, STTProviders.ASSEMBLYAI.value, "model"):
        VoiceConfigFieldCatalog(
            _named_options(
                ("u3-rt-pro", "Universal-3 Pro Streaming"),
                ("universal-streaming-english", "Universal Streaming · English"),
                (
                    "universal-streaming-multilingual",
                    "Universal Streaming · Multilingual",
                ),
                ("whisper-rt", "Whisper Streaming"),
            )
        ),
    (VoiceKind.STT, STTProviders.CARTESIA.value, "model"):
        VoiceConfigFieldCatalog(_options("ink-whisper"), allow_custom=True),
    (VoiceKind.STT, STTProviders.CARTESIA.value, "language"):
        VoiceConfigFieldCatalog(_ISO_LANGUAGES, allow_custom=True),
    (VoiceKind.STT, STTProviders.GOOGLE.value, "model"):
        VoiceConfigFieldCatalog(
            _options(
                "latest_long",
                "latest_short",
                "command_and_search",
                "phone_call",
                "video",
                "default",
            )
        ),
    (VoiceKind.STT, STTProviders.GOOGLE.value, "language"):
        VoiceConfigFieldCatalog(_COMMON_LOCALES, allow_custom=True),
    (VoiceKind.STT, STTProviders.GLADIA.value, "language"):
        VoiceConfigFieldCatalog(_ISO_LANGUAGES, allow_custom=True),
    (VoiceKind.STT, STTProviders.REVAI.value, "language"):
        VoiceConfigFieldCatalog(_ISO_LANGUAGES, allow_custom=True),
    (VoiceKind.STT, STTProviders.SPEECHMATICS.value, "language"):
        VoiceConfigFieldCatalog(_ISO_LANGUAGES, allow_custom=True),
    (VoiceKind.TTS, TTSProviders.AMAZON_POLLY.value, "model"):
        VoiceConfigFieldCatalog(
            _named_options(
                ("standard", "Standard engine"),
                ("neural", "Neural engine"),
                ("long-form", "Long-form engine"),
                ("generative", "Generative engine"),
            )
        ),
    (VoiceKind.TTS, TTSProviders.AMAZON_POLLY.value, "voice"):
        VoiceConfigFieldCatalog(_POLLY_VOICES, allow_custom=True),
    (VoiceKind.TTS, TTSProviders.AMAZON_POLLY.value, "language"):
        VoiceConfigFieldCatalog(_POLLY_LANGUAGES, allow_custom=True),
    (VoiceKind.TTS, TTSProviders.ELEVENLABS.value, "model"):
        VoiceConfigFieldCatalog(
            _named_options(
                ("eleven_v3", "Eleven v3"),
                ("eleven_multilingual_v2", "Eleven Multilingual v2"),
                ("eleven_flash_v2_5", "Eleven Flash v2.5"),
                ("eleven_flash_v2", "Eleven Flash v2"),
            ),
            allow_custom=True,
        ),
    (VoiceKind.TTS, TTSProviders.ELEVENLABS.value, "voice"):
        VoiceConfigFieldCatalog(_ELEVENLABS_VOICES, allow_custom=True),
    (VoiceKind.TTS, TTSProviders.ELEVENLABS.value, "language"):
        VoiceConfigFieldCatalog(_ISO_LANGUAGES, allow_custom=True),
    (VoiceKind.TTS, TTSProviders.CARTESIA.value, "model"):
        VoiceConfigFieldCatalog(
            _options("sonic-3.5", "sonic-3.5-2026-05-04", "sonic-latest", "sonic-3"),
            allow_custom=True,
        ),
    (VoiceKind.TTS, TTSProviders.CARTESIA.value, "voice"):
        VoiceConfigFieldCatalog(
            _named_options(
                ("6f84f4b8-58a2-430c-8c79-688dad597532", "California Girl"),
                ("6ccbfb76-1fc6-48f7-b71d-91ac6298247b", "Tessa"),
                ("aef96ff9-4578-4b5d-9744-7fb347cbe4d4", "Holly"),
                ("f786b574-daa5-4673-aa0c-cbe3e8534c02", "Katie"),
                ("a5136bf9-224c-4d76-b823-52bd5efcffcc", "Jameson"),
            ),
            allow_custom=True,
        ),
    (VoiceKind.TTS, TTSProviders.CARTESIA.value, "language"):
        VoiceConfigFieldCatalog(_ISO_LANGUAGES, allow_custom=True),
    (VoiceKind.TTS, TTSProviders.SARVAM.value, "model"):
        VoiceConfigFieldCatalog(_options("bulbul:v3", "bulbul:v2")),
    (VoiceKind.TTS, TTSProviders.SARVAM.value, "voice"):
        VoiceConfigFieldCatalog(_SARVAM_VOICES),
    (VoiceKind.TTS, TTSProviders.SARVAM.value, "language"):
        VoiceConfigFieldCatalog(_SARVAM_LANGUAGES),
    (VoiceKind.TTS, TTSProviders.OPENAI.value, "model"):
        VoiceConfigFieldCatalog(
            _named_options(
                ("gpt-4o-mini-tts", "GPT-4o mini TTS"),
                ("tts-1", "TTS-1 · lower latency"),
                ("tts-1-hd", "TTS-1 HD · higher quality"),
            )
        ),
    (VoiceKind.TTS, TTSProviders.OPENAI.value, "voice"):
        VoiceConfigFieldCatalog(_OPENAI_VOICES),
    (VoiceKind.TTS, TTSProviders.DEEPGRAM.value, "model"):
        VoiceConfigFieldCatalog(_DEEPGRAM_TTS_MODELS, allow_custom=True),
    (VoiceKind.TTS, TTSProviders.GROQ.value, "model"):
        VoiceConfigFieldCatalog(
            _named_options(
                ("canopylabs/orpheus-v1-english", "Orpheus · English"),
                ("canopylabs/orpheus-arabic-saudi", "Orpheus · Arabic (Saudi)"),
            )
        ),
    (VoiceKind.TTS, TTSProviders.GROQ.value, "voice"):
        VoiceConfigFieldCatalog(
            _named_options(
                ("autumn", "Autumn · English"),
                ("diana", "Diana · English"),
                ("hannah", "Hannah · English"),
                ("austin", "Austin · English"),
                ("daniel", "Daniel · English"),
                ("troy", "Troy · English"),
                ("abdullah", "Abdullah · Arabic"),
                ("fahad", "Fahad · Arabic"),
                ("sultan", "Sultan · Arabic"),
                ("lulwa", "Lulwa · Arabic"),
                ("noura", "Noura · Arabic"),
                ("aisha", "Aisha · Arabic"),
            )
        ),
    (VoiceKind.TTS, TTSProviders.RIME.value, "model"):
        VoiceConfigFieldCatalog(
            _options("arcana", "arcanav2", "mistv3", "mistv2", "mist")
        ),
    (VoiceKind.TTS, TTSProviders.RIME.value, "voice"):
        VoiceConfigFieldCatalog(
            _options("astra", "celeste", "orion", "luna", "peak", "amber"),
            allow_custom=True,
        ),
    (VoiceKind.TTS, TTSProviders.SMALLEST.value, "model"):
        VoiceConfigFieldCatalog(_options("lightning-v2")),
    (VoiceKind.TTS, TTSProviders.SMALLEST.value, "voice"):
        VoiceConfigFieldCatalog(
            _options("meher", "magnus", "emily"),
            allow_custom=True,
        ),
    (VoiceKind.TTS, TTSProviders.SMALLEST.value, "language"):
        VoiceConfigFieldCatalog(_ISO_LANGUAGES, allow_custom=True),
    (VoiceKind.TTS, TTSProviders.HUME.value, "model"):
        VoiceConfigFieldCatalog(
            _named_options(
                ("octave-2-preview", "Octave 2 · preview"),
                ("octave-1", "Octave 1"),
            ),
            allow_custom=True,
        ),
    (VoiceKind.TTS, TTSProviders.HUME.value, "language"):
        VoiceConfigFieldCatalog(_ISO_LANGUAGES, allow_custom=True),
    (VoiceKind.TTS, TTSProviders.MURF.value, "voice"):
        VoiceConfigFieldCatalog(
            _options(
                "Alicia",
                "Alina",
                "Ariana",
                "Caleb",
                "Daisy",
                "Delilah",
                "Edmund",
                "Ezekiel",
                "Gordon",
                "Harold",
                "Heather",
                "Isabelle",
                "Jayden",
                "Benedict",
                "Jake",
                "Lydia",
                "Abhinav",
                "Anisha",
                "Anusha",
                "Nikhil",
                "Palak",
                "Pooja",
                "Samar",
                "Harper",
                "Ivy",
                "Jimm",
            ),
            allow_custom=True,
        ),
    (VoiceKind.REALTIME, RealtimeProviders.GEMINI_LIVE.value, "model"):
        VoiceConfigFieldCatalog(_options("gemini-3.1-flash-live-preview")),
    (VoiceKind.REALTIME, RealtimeProviders.GEMINI_LIVE.value, "voice"):
        VoiceConfigFieldCatalog(_GEMINI_VOICES),
    (VoiceKind.REALTIME, RealtimeProviders.OPENAI_REALTIME.value, "model"):
        VoiceConfigFieldCatalog(_options("gpt-realtime", "gpt-realtime-mini")),
    (VoiceKind.REALTIME, RealtimeProviders.OPENAI_REALTIME.value, "voice"):
        VoiceConfigFieldCatalog(
            _options(
                "alloy",
                "ash",
                "ballad",
                "coral",
                "echo",
                "sage",
                "shimmer",
                "verse",
                "marin",
                "cedar",
            )
        ),
    (
        VoiceKind.REALTIME,
        RealtimeProviders.OPENAI_REALTIME.value,
        "input_transcription_model",
    ): VoiceConfigFieldCatalog(
        _options(
            "whisper-1",
            "gpt-4o-mini-transcribe",
            "gpt-4o-mini-transcribe-2025-12-15",
            "gpt-4o-transcribe",
            "gpt-4o-transcribe-diarize",
        )
    ),
}


def voice_config_field_catalog(
    kind: VoiceKind,
    provider: str,
    field: str,
) -> VoiceConfigFieldCatalog | None:
    """Return published choices for one voice config field, if finite enough."""
    return _VOICE_FIELD_CATALOGS.get((kind, provider, field))
