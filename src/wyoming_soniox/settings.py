"""Server settings shared by CLI and handlers."""

from dataclasses import dataclass, field

# https://docs.soniox.com/stt/concepts/supported-languages
STT_LANGUAGES = [
    "af", "ar", "az", "be", "bg", "bn", "bs", "ca", "cs", "cy", "da", "de", "el", "en", "es", "et",
    "eu", "fa", "fi", "fr", "gl", "gu", "he", "hi", "hr", "hu", "id", "it", "ja", "kk", "kn", "ko",
    "lt", "lv", "mk", "ml", "mr", "ms", "nl", "no", "pa", "pl", "pt", "ro", "ru", "sk", "sl", "sq",
    "sr", "sv", "sw", "ta", "te", "th", "tl", "tr", "uk", "ur", "vi", "zh",
]  # fmt: skip

STT_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
TTS_URL = "wss://tts-rt.soniox.com/tts-websocket"
TTS_MODELS_URL = "https://api.soniox.com/v1/tts-models"


@dataclass
class SttSettings:
    """Soniox real-time speech-to-text settings."""

    model: str = "stt-rt-v5"
    language: str = "ru"
    """Used when the client does not send a supported language."""

    language_hints_strict: bool = True
    context_terms: list[str] = field(default_factory=list)
    context_text: str = ""
    endpoint_latency_adjustment_level: int = 2
    endpoint_sensitivity: float = 0.3
    max_endpoint_delay_ms: int = 1500
    wake_words: list[str] = field(default_factory=list)
    """Wake word phrases to cut from the start of the transcript, with anything before them.

    For satellites that send the buffered audio including the wake word.
    """

    wake_word_window_ms: int = 3000
    """The wake word is only looked for among words starting this early in the audio."""

    max_utterance_s: float = 15.0
    """Safety limit: finalize the utterance if Soniox has not detected its end by then."""

    url: str = STT_URL

    debug_audio_dir: str = ""
    """Save the audio of each session as WAV here (debugging only)."""


@dataclass
class TtsSettings:
    """Soniox real-time text-to-speech settings."""

    enabled: bool = True
    model: str = ""
    """Empty: the first model reported by Soniox."""

    voice: str = ""
    """Used when the client does not request a known voice. Empty: the first voice of the model."""

    language: str = "ru"
    """Language of the synthesized speech: Wyoming clients send a voice name, not a language."""

    speed: float = 1.0
    sample_rate: int = 24000
    url: str = TTS_URL
    models_url: str = TTS_MODELS_URL


@dataclass
class Settings:
    """All server settings."""

    api_key: str
    uri: str = "tcp://0.0.0.0:10300"
    stt: SttSettings = field(default_factory=SttSettings)
    tts: TtsSettings = field(default_factory=TtsSettings)
