"""Text-to-speech over the Soniox real-time WebSocket API."""

import asyncio
import base64
import itertools
import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from . import __version__
from .settings import STT_LANGUAGES, TtsSettings
from .soniox_stt import SonioxError

_LOGGER = logging.getLogger(__name__)

CATALOG_RETRY_S = 300.0
MAX_TEXT_CHARS = 5000
_stream_ids = itertools.count(1)
# Soniox speaks the same 60 languages it recognizes (docs.soniox.com: tts supported languages).
TTS_LANGUAGES = STT_LANGUAGES


@dataclass
class TtsVoiceInfo:
    """Soniox voice: `id` goes to the `voice` field of a request."""

    id: str
    gender: str = ""
    description: str = ""


@dataclass
class TtsCatalog:
    """Model, languages and voices Soniox offers; empty until loaded."""

    model: str = ""
    languages: list[str] = field(default_factory=list)
    voices: list[TtsVoiceInfo] = field(default_factory=list)
    default_voice: str = ""

    @property
    def loaded(self) -> bool:
        return bool(self.model and self.voices)

    def resolve_voice(self, requested: str | None) -> str:
        if requested and any(voice.id == requested for voice in self.voices):
            return requested
        return self.default_voice


def _fetch_models(api_key: str, url: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": f"wyoming-soniox/{__version__}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)["models"]
    except urllib.error.HTTPError as err:
        body = err.read().decode(errors="replace")[:300]
        raise SonioxError(f"HTTP {err.code}: {body}", error_type=str(err.code)) from err


DEFAULT_MODEL = "tts-rt-v2"
PROBE_TIMEOUT_S = 15.0

# Voices of the Soniox models (docs.soniox.com: get_tts_models), all checked with tts-rt-v2.
# Used when the models API is not available to the key: it needs a separate permission.
BUILTIN_VOICES = [
    TtsVoiceInfo("Maya", "female", "Steady, clear and warm"),
    TtsVoiceInfo("Daniel", "male", "Rich, steady and reassuring"),
    TtsVoiceInfo("Noah", "male", "Lively, youthful and upbeat"),
    TtsVoiceInfo("Nina", "female", "Bright, expressive and friendly"),
    TtsVoiceInfo("Emma", "female", "Smooth, relaxed and personable"),
    TtsVoiceInfo("Jack", "male", "Friendly, confident and clear"),
    TtsVoiceInfo("Adrian", "male", "Deep, focused and authoritative"),
    TtsVoiceInfo("Claire", "female", "Polished, articulate and refined"),
    TtsVoiceInfo("Grace", "female", "Gentle, soothing and calm"),
    TtsVoiceInfo("Owen", "male", "Grounded, even-paced and composed"),
    TtsVoiceInfo("Mina", "female", "Soft, thoughtful and sincere"),
    TtsVoiceInfo("Kenji", "male", "Calm, precise and trustworthy"),
    TtsVoiceInfo("Rafael", "male", "Composed, warm Spanish accent"),
    TtsVoiceInfo("Mateo", "male", "Youthful, soft Spanish accent"),
    TtsVoiceInfo("Lucia", "female", "Mature, natural Spanish accent"),
    TtsVoiceInfo("Sofia", "female", "Friendly, Spanish accent"),
    TtsVoiceInfo("Oliver", "male", "Refined, smooth British accent"),
    TtsVoiceInfo("Arthur", "male", "Deep, rich British accent"),
    TtsVoiceInfo("Isla", "female", "Lively, bright British accent"),
    TtsVoiceInfo("Victoria", "female", "Poised, refined British accent"),
    TtsVoiceInfo("Cooper", "male", "Bold, strong Australian accent"),
    TtsVoiceInfo("Mason", "male", "Relaxed, Australian accent"),
    TtsVoiceInfo("Ruby", "female", "Confident, Australian accent"),
    TtsVoiceInfo("Elise", "female", "Warm, Australian accent"),
    TtsVoiceInfo("Arjun", "male", "Deep, Indian accent"),
    TtsVoiceInfo("Rohan", "male", "Lively, Indian accent"),
    TtsVoiceInfo("Priya", "female", "Clear, Indian accent"),
    TtsVoiceInfo("Meera", "female", "Polished, Indian accent"),
]


def _pick_default_voice(catalog: TtsCatalog, voice: str, language_name: str = "") -> None:
    """The configured voice; else a voice native to the speech language (its description names the
    language, e.g. "A neutral Russian male voice"); else the first one."""
    catalog.default_voice = catalog.voices[0].id
    if language_name and not voice:
        native = next(
            (v for v in catalog.voices if language_name.lower() in v.description.lower()), None
        )
        if native is not None:
            catalog.default_voice = native.id
    if voice:
        if any(v.id == voice for v in catalog.voices):
            catalog.default_voice = voice
        else:
            _LOGGER.warning("TTS voice %r is not offered, using %r", voice, catalog.default_voice)


async def _catalog_from_api(api_key: str, settings: TtsSettings) -> TtsCatalog:
    models = await asyncio.to_thread(_fetch_models, api_key, settings.models_url)
    by_id = {m["id"]: m for m in models}
    model = by_id.get(settings.model) or by_id.get(DEFAULT_MODEL) or models[0]
    if settings.model and settings.model not in by_id:
        _LOGGER.warning("TTS model %r is not offered, using %r", settings.model, model["id"])
    catalog = TtsCatalog(
        model=model["id"],
        languages=[language["code"] for language in model["languages"]],
        voices=[
            TtsVoiceInfo(v["id"], v.get("gender", ""), v.get("description", ""))
            for v in model["voices"]
        ],
    )
    names = {language["code"]: language.get("name", "") for language in model["languages"]}
    _pick_default_voice(catalog, settings.voice, names.get(settings.language, ""))
    return catalog


async def probe_tts(api_key: str, settings: TtsSettings, model: str, voice: str) -> None:
    """Open a stream and cancel it before any text: checks the key and the model, costs nothing."""
    try:
        async with connect(
            settings.url,
            additional_headers={"Authorization": f"Bearer {api_key}"},
            open_timeout=PROBE_TIMEOUT_S,
        ) as ws:
            config = {
                "stream_id": "probe",
                "model": model,
                "language": settings.language,
                "voice": voice,
                "audio_format": "pcm_s16le",
                "sample_rate": settings.sample_rate,
            }
            await ws.send(json.dumps(config))
            await ws.send(json.dumps({"stream_id": "probe", "cancel": True}))
            async with asyncio.timeout(PROBE_TIMEOUT_S):
                async for message in ws:
                    data = json.loads(message)
                    if "error_type" in data or "error_code" in data:
                        raise SonioxError(
                            f"{data.get('error_code')} {data.get('error_type')}: "
                            f"{data.get('error_message')}",
                            error_type=str(data.get("error_type") or data.get("error_code")),
                        )
                    if data.get("terminated"):
                        return
    except SonioxError:
        raise
    except Exception as err:  # noqa: BLE001 - rejected handshake, DNS, TLS, timeout, ...
        raise SonioxError(f"{type(err).__name__}: {err}") from err


async def load_catalog(api_key: str, settings: TtsSettings) -> TtsCatalog:
    """Model, languages and voices from the models API, else built in once a probe passes."""
    try:
        return await _catalog_from_api(api_key, settings)
    except Exception as err:  # noqa: BLE001 - the models API needs its own key permission
        _LOGGER.info("TTS models API is not available (%s), using the built-in voice list", err)
    catalog = TtsCatalog(
        model=settings.model or DEFAULT_MODEL,
        languages=list(TTS_LANGUAGES),
        voices=list(BUILTIN_VOICES),
    )
    _pick_default_voice(catalog, settings.voice)
    await probe_tts(api_key, settings, catalog.model, catalog.default_voice)
    return catalog


async def keep_catalog_loaded(api_key: str, settings: TtsSettings, catalog: TtsCatalog) -> None:
    """Load the catalog in the background, retrying until it succeeds."""
    while not catalog.loaded:
        try:
            loaded = await load_catalog(api_key, settings)
        except Exception as err:  # noqa: BLE001 - keep retrying, the STT part works anyway
            _LOGGER.warning(
                "Text-to-speech is unavailable, retrying in %.0f s: %s", CATALOG_RETRY_S, err
            )
            await asyncio.sleep(CATALOG_RETRY_S)
            continue
        catalog.model, catalog.languages = loaded.model, loaded.languages
        catalog.voices, catalog.default_voice = loaded.voices, loaded.default_voice
        _LOGGER.info(
            "Text-to-speech: model %s, %d voices, default voice %s",
            catalog.model,
            len(catalog.voices),
            catalog.default_voice,
        )


class TtsSession:
    """One synthesis request: text in (whole or streamed in pieces), PCM s16le mono audio out.

    Soniox ends a stream with `request_timeout` when text stops coming for a few seconds
    (an LLM calling a tool, for example). The next piece of text then starts a new stream,
    on a new connection if Soniox has closed the idle one.
    """

    def __init__(
        self,
        api_key: str,
        settings: TtsSettings,
        model: str,
        voice: str,
        on_audio: Callable[[bytes], Awaitable[None]],
    ) -> None:
        self._api_key = api_key
        self._settings = settings
        self._model = model
        self._voice = voice
        self._on_audio = on_audio
        self._ws: ClientConnection | None = None
        self._reader: asyncio.Task | None = None
        self._stream_id: str | None = None
        self._terminated: dict[str, asyncio.Event] = {}
        self._error: SonioxError | None = None
        self._odd_byte = b""
        self._started = time.monotonic()
        self._first_audio_s: float | None = None
        self.audio_bytes = 0

    async def connect(self) -> None:
        """Open the connection in advance; text can arrive later."""
        await self._ensure_connected()

    async def add_text(self, text: str) -> None:
        """Send a piece of text for synthesis."""
        self._raise_error()
        if not text:
            return
        for start in range(0, len(text), MAX_TEXT_CHARS):
            await self._send_text(text[start : start + MAX_TEXT_CHARS], text_end=False)

    async def finish(self) -> None:
        """Mark the end of text and wait until all audio has been delivered."""
        self._raise_error()
        if self._stream_id is not None:
            stream_id = self._stream_id
            await self._send({"stream_id": stream_id, "text": "", "text_end": True})
            await self._terminated[stream_id].wait()
            self._stream_id = None
        self._raise_error()
        _LOGGER.debug(
            "Synthesized %.2f s of audio, first audio after %s s",
            self.audio_bytes / (self._settings.sample_rate * 2),
            f"{self._first_audio_s:.2f}" if self._first_audio_s is not None else "-",
        )

    async def close(self) -> None:
        """Close the connection, dropping any audio still in flight."""
        if self._reader is not None:
            self._reader.cancel()
            await asyncio.gather(self._reader, return_exceptions=True)
        if self._ws is not None:
            await self._ws.close()

    def _raise_error(self) -> None:
        if self._error is not None:
            raise self._error

    async def _ensure_connected(self) -> None:
        if self._ws is not None and self._reader is not None and not self._reader.done():
            return
        try:
            self._ws = await connect(
                self._settings.url,
                additional_headers={"Authorization": f"Bearer {self._api_key}"},
                compression=None,
            )
        except Exception as err:  # noqa: BLE001 - rejected handshake, DNS, TLS, ...
            raise SonioxError(f"Cannot connect to Soniox TTS: {type(err).__name__}: {err}") from err
        _LOGGER.debug("Connected to Soniox TTS in %.3f s", time.monotonic() - self._started)
        self._reader = asyncio.create_task(self._read(self._ws), name="soniox tts reader")

    async def _send_text(self, text: str, text_end: bool) -> None:
        if self._stream_id is None or self._terminated[self._stream_id].is_set():
            await self._start_stream()
        assert self._stream_id is not None
        await self._send({"stream_id": self._stream_id, "text": text, "text_end": text_end})

    async def _start_stream(self) -> None:
        await self._ensure_connected()
        stream_id = f"s{next(_stream_ids)}"
        self._stream_id = stream_id
        self._terminated[stream_id] = asyncio.Event()
        config = {
            "stream_id": stream_id,
            "model": self._model,
            "language": self._settings.language,
            "voice": self._voice,
            "audio_format": "pcm_s16le",
            "sample_rate": self._settings.sample_rate,
        }
        if self._settings.speed != 1.0:
            config["speed"] = self._settings.speed
        await self._send(config)

    async def _send(self, message: dict[str, Any]) -> None:
        assert self._ws is not None
        try:
            await self._ws.send(json.dumps(message, ensure_ascii=False))
        except ConnectionClosed as err:
            raise SonioxError(f"Connection closed: {err}") from err

    async def _read(self, ws: ClientConnection) -> None:
        try:
            async for message in ws:
                data = json.loads(message)
                stream_id = data.get("stream_id")
                if "error_type" in data or "error_code" in data:
                    self._handle_error(stream_id, data)
                if data.get("audio"):
                    await self._deliver(base64.b64decode(data["audio"]))
                if data.get("terminated") and stream_id in self._terminated:
                    self._terminated[stream_id].set()
        except ConnectionClosed:
            pass
        finally:
            # Streams of a closed connection are over; waiting callers must not hang.
            if self._stream_id is not None and not self._terminated[self._stream_id].is_set():
                if self._error is None:
                    self._error = SonioxError("Connection closed before the audio ended")
            for event in self._terminated.values():
                event.set()

    def _handle_error(self, stream_id: str | None, data: dict[str, Any]) -> None:
        error_type = str(data.get("error_type") or data.get("error_code"))
        message = (
            f"{data.get('error_code')} {error_type}: {data.get('error_message')} "
            f"(request_id={data.get('request_id')})"
        )
        if error_type == "request_timeout" and stream_id == self._stream_id:
            # Text paused for too long; the next piece of text starts a new stream.
            _LOGGER.debug("Stream %s timed out waiting for text", stream_id)
            return
        _LOGGER.error("Soniox TTS error: %s", message)
        if self._error is None:
            self._error = SonioxError(message, error_type=error_type)

    async def _deliver(self, audio: bytes) -> None:
        # Forward whole 16-bit samples only.
        audio = self._odd_byte + audio
        if len(audio) % 2:
            audio, self._odd_byte = audio[:-1], audio[-1:]
        else:
            self._odd_byte = b""
        if not audio:
            return
        if self._first_audio_s is None:
            self._first_audio_s = time.monotonic() - self._started
        self.audio_bytes += len(audio)
        await self._on_audio(audio)
