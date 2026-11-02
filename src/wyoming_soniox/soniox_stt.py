"""One streaming recognition session with the Soniox real-time WebSocket API."""

import asyncio
import bisect
import json
import logging
import time
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from .settings import SttSettings
from .wake_word import Token, strip_wake_word

_LOGGER = logging.getLogger(__name__)

END_TOKEN = "<end>"
FIN_TOKEN = "<fin>"
BYTES_PER_SECOND = 16000 * 2

_FINALIZE = object()


class SonioxError(Exception):
    """Soniox returned an error or the connection failed."""

    def __init__(self, message: str, error_type: str = "connection_error") -> None:
        super().__init__(message)
        self.error_type = error_type


class SttSession:
    """Streams audio to Soniox and resolves with the text of the first utterance.

    The utterance ends when Soniox detects an endpoint (<end>), after a requested
    finalize (<fin>) or when Soniox finishes the stream. An endpoint right after the
    wake word (nothing else said yet) does not end the utterance.
    """

    def __init__(self, api_key: str, settings: SttSettings, language: str) -> None:
        self._api_key = api_key
        self._settings = settings
        self._language = language
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._final_tokens: list[Token] = []
        self._finalize_requested = False
        self._audio_bytes = 0
        # Audio offset (bytes) at the end of each received chunk and when it arrived; clients may
        # send buffered audio faster than real time, so offsets alone do not give wall time.
        self._chunk_ends: list[int] = []
        self._chunk_times: list[float] = []
        self._speech_end_ms = 0
        self._debug_audio = bytearray() if settings.debug_audio_dir else None
        self._started = time.monotonic()
        self.result: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._task = asyncio.create_task(self._run(), name="soniox stt session")

    @property
    def raw_text(self) -> str:
        """Final text received so far, as recognized."""
        return "".join(token.text for token in self._final_tokens).strip()

    @property
    def text(self) -> str:
        """Final text received so far, without the wake word."""
        return self._strip_wake_word()[0]

    def _strip_wake_word(self) -> tuple[str, bool]:
        if not self._settings.wake_words:
            return self.raw_text, False
        return strip_wake_word(
            self._final_tokens, self._settings.wake_words, self._settings.wake_word_window_ms
        )

    def delay_after_speech(self) -> float:
        """Seconds since the chunk containing the end of the last final word arrived."""
        offset = self._speech_end_ms * BYTES_PER_SECOND // 1000
        index = bisect.bisect_left(self._chunk_ends, offset)
        if index >= len(self._chunk_times):
            return 0.0
        return time.monotonic() - self._chunk_times[index]

    def send_audio(self, audio: bytes) -> None:
        """Queue raw PCM s16le 16 kHz mono audio."""
        if not self.result.done():
            self._audio_bytes += len(audio)
            self._chunk_ends.append(self._audio_bytes)
            self._chunk_times.append(time.monotonic())
            if self._debug_audio is not None:
                self._debug_audio.extend(audio)
            self._queue.put_nowait(audio)

    def finalize(self) -> None:
        """Ask Soniox to finalize everything sent so far."""
        if not self._finalize_requested and not self.result.done():
            self._finalize_requested = True
            self._queue.put_nowait(_FINALIZE)

    async def close(self) -> None:
        """Stop the session and close the connection."""
        # Before any await: the caller may be cancelled when the client disconnects.
        if self._debug_audio:
            self._save_debug_audio()
        if not self._task.done():
            self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        if not self.result.done():
            self.result.cancel()

    def _save_debug_audio(self) -> None:
        assert self._debug_audio is not None
        directory = Path(self._settings.debug_audio_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{datetime.now():%Y%m%d-%H%M%S-%f}.wav"
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(bytes(self._debug_audio))
        self._debug_audio = None
        _LOGGER.debug("Saved session audio to %s", path)

    def _config(self) -> dict[str, Any]:
        s = self._settings
        config: dict[str, Any] = {
            "model": s.model,
            "audio_format": "pcm_s16le",
            "sample_rate": 16000,
            "num_channels": 1,
            "language_hints": [self._language],
            "language_hints_strict": s.language_hints_strict,
            "enable_endpoint_detection": True,
            "endpoint_latency_adjustment_level": s.endpoint_latency_adjustment_level,
            "endpoint_sensitivity": s.endpoint_sensitivity,
            "max_endpoint_delay_ms": s.max_endpoint_delay_ms,
        }
        context: dict[str, Any] = {}
        terms = s.context_terms + [w for w in s.wake_words if w not in s.context_terms]
        if terms:
            context["terms"] = terms
        if s.context_text:
            context["text"] = s.context_text
        if context:
            config["context"] = context
        return config

    async def _run(self) -> None:
        try:
            async with connect(
                self._settings.url,
                additional_headers={"Authorization": f"Bearer {self._api_key}"},
                compression=None,
            ) as ws:
                _LOGGER.debug("Connected to Soniox in %.3f s", time.monotonic() - self._started)
                await ws.send(json.dumps(self._config()))
                sender = asyncio.create_task(self._send(ws))
                try:
                    await self._receive(ws)
                finally:
                    sender.cancel()
                    await asyncio.gather(sender, return_exceptions=True)
        except asyncio.CancelledError:
            raise
        except SonioxError as err:
            self._set_error(err)
        except Exception as err:  # noqa: BLE001 - any connection problem fails the session
            self._set_error(SonioxError(f"{type(err).__name__}: {err}"))

    async def _send(self, ws: ClientConnection) -> None:
        while True:
            item = await self._queue.get()
            if item is _FINALIZE:
                await ws.send(json.dumps({"type": "finalize"}))
            else:
                await ws.send(item)

    async def _receive(self, ws: ClientConnection) -> None:
        try:
            async for message in ws:
                data = json.loads(message)
                if "error_code" in data or "error_type" in data:
                    raise SonioxError(
                        f"{data.get('error_code')} {data.get('error_type')}: "
                        f"{data.get('error_message')} (request_id={data.get('request_id')})",
                        error_type=str(data.get("error_type") or data.get("error_code")),
                    )
                for token in data.get("tokens", []):
                    if not token.get("is_final"):
                        continue
                    text = token.get("text", "")
                    if text == END_TOKEN and self._only_wake_word():
                        _LOGGER.debug("Endpoint after the wake word only, keep listening")
                        continue
                    if text in (END_TOKEN, FIN_TOKEN):
                        self._set_result(text)
                        return
                    self._final_tokens.append(Token(text, token.get("start_ms", 0)))
                    if text.strip() and "end_ms" in token:
                        self._speech_end_ms = token["end_ms"]
                if data.get("finished"):
                    self._set_result("finished")
                    return
        except ConnectionClosed as err:
            raise SonioxError(f"Connection closed: {err}") from err
        raise SonioxError("Connection closed before the result")

    def _only_wake_word(self) -> bool:
        text, found = self._strip_wake_word()
        return found and not text

    def _set_result(self, reason: str) -> None:
        if self.result.done():
            return
        _LOGGER.info(
            "Utterance ended by %s: last word ended at %.2f s of %.2f s audio, "
            "result %.2f s after that audio arrived",
            reason,
            self._speech_end_ms / 1000,
            self._audio_bytes / BYTES_PER_SECOND,
            self.delay_after_speech(),
        )
        _LOGGER.debug("Text: %r (recognized: %r)", self.text, self.raw_text)
        self.result.set_result(self.text)

    def _set_error(self, err: SonioxError) -> None:
        if not self.result.done():
            self.result.set_exception(err)
