"""Wyoming event handler: one instance per client connection."""

import asyncio
import logging
import time
from collections.abc import Callable

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped,
)

from .settings import STT_LANGUAGES, Settings
from .soniox_stt import SonioxError, SttSession
from .soniox_tts import TtsCatalog, TtsSession

_LOGGER = logging.getLogger(__name__)

FINALIZE_TIMEOUT_S = 5.0


class SonioxEventHandler(AsyncEventHandler):
    """Speech-to-text and text-to-speech over Soniox.

    A client may run several requests in a row on one connection.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        settings: Settings,
        info: Callable[[], Info],
        catalog: TtsCatalog,
    ) -> None:
        super().__init__(reader, writer)
        self._settings = settings
        self._info = info
        self._catalog = catalog
        self._converter = AudioChunkConverter(rate=16000, width=2, channels=1)
        self._session: SttSession | None = None
        self._result_task: asyncio.Task | None = None
        self._tts: TtsSession | None = None
        self._tts_streaming = False
        self._tts_audio_started = False

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self._info().event())
        elif Synthesize.is_type(event.type):
            # Clients that stream text send the whole text too, for servers without streaming.
            if not self._tts_streaming:
                await self._synthesize(Synthesize.from_event(event))
        elif SynthesizeStart.is_type(event.type):
            await self._start_tts_stream(SynthesizeStart.from_event(event))
        elif SynthesizeChunk.is_type(event.type):
            await self._add_tts_text(SynthesizeChunk.from_event(event).text)
        elif SynthesizeStop.is_type(event.type):
            await self._stop_tts_stream()
        elif Transcribe.is_type(event.type):
            await self._start_session(Transcribe.from_event(event).language)
        elif AudioStart.is_type(event.type):
            if self._session is None:
                await self._start_session(None)
        elif AudioChunk.is_type(event.type):
            if self._session is not None:
                chunk = self._converter.convert(AudioChunk.from_event(event))
                self._session.send_audio(chunk.audio)
        elif AudioStop.is_type(event.type):
            if self._session is not None:
                self._session.finalize()
        return True

    async def disconnect(self) -> None:
        await self._stop_session()
        await self._close_tts()

    # Text-to-speech

    async def _open_tts(self, voice: str | None) -> TtsSession | None:
        await self._close_tts()
        if not self._catalog.loaded:
            await self.write_event(
                Error(text="Text-to-speech is not available", code="tts_unavailable").event()
            )
            return None
        self._tts_audio_started = False
        self._tts = TtsSession(
            self._settings.api_key,
            self._settings.tts,
            self._catalog.model,
            self._catalog.resolve_voice(voice),
            self._write_tts_audio,
        )
        return self._tts

    async def _write_tts_audio(self, audio: bytes) -> None:
        rate = self._settings.tts.sample_rate
        if not self._tts_audio_started:
            self._tts_audio_started = True
            await self.write_event(AudioStart(rate=rate, width=2, channels=1).event())
        await self.write_event(AudioChunk(rate=rate, width=2, channels=1, audio=audio).event())

    async def _end_tts_audio(self) -> None:
        if not self._tts_audio_started:
            rate = self._settings.tts.sample_rate
            await self.write_event(AudioStart(rate=rate, width=2, channels=1).event())
        await self.write_event(AudioStop().event())

    async def _close_tts(self) -> None:
        if self._tts is not None:
            await self._tts.close()
            self._tts = None

    async def _tts_error(self, err: SonioxError) -> None:
        _LOGGER.error("Soniox TTS error: %s", err)
        # A stream stays open until synthesize-stop so the trailing synthesize is still ignored.
        await self._close_tts()
        await self.write_event(Error(text=str(err), code=err.error_type).event())

    async def _synthesize(self, synthesize: Synthesize) -> None:
        started = time.monotonic()
        session = await self._open_tts(synthesize.voice.name if synthesize.voice else None)
        if session is None:
            return
        try:
            await session.add_text(synthesize.text)
            await session.finish()
        except SonioxError as err:
            await self._tts_error(err)
            return
        await self._end_tts_audio()
        await self._close_tts()
        _LOGGER.info(
            "Synthesized %d chars in %.2f s", len(synthesize.text), time.monotonic() - started
        )

    async def _start_tts_stream(self, start: SynthesizeStart) -> None:
        self._tts_streaming = True
        session = await self._open_tts(start.voice.name if start.voice else None)
        if session is None:
            return
        try:
            # Connect while the text is still being generated.
            await session.connect()
        except SonioxError as err:
            await self._tts_error(err)

    async def _add_tts_text(self, text: str) -> None:
        if self._tts is None or not self._tts_streaming:
            return
        try:
            await self._tts.add_text(text)
        except SonioxError as err:
            await self._tts_error(err)

    async def _stop_tts_stream(self) -> None:
        was_streaming, self._tts_streaming = self._tts_streaming, False
        if self._tts is None or not was_streaming:
            return
        try:
            await self._tts.finish()
        except SonioxError as err:
            await self._tts_error(err)
            return
        await self._end_tts_audio()
        await self.write_event(SynthesizeStopped().event())
        await self._close_tts()

    # Speech-to-text

    def _resolve_language(self, language: str | None) -> str:
        code = (language or "").replace("_", "-").split("-")[0].lower()
        if code in STT_LANGUAGES:
            return code
        if code:
            _LOGGER.warning(
                "Language %r is not supported, using %r", language, self._settings.stt.language
            )
        return self._settings.stt.language

    async def _start_session(self, language: str | None) -> None:
        await self._stop_session()
        session = SttSession(
            self._settings.api_key, self._settings.stt, self._resolve_language(language)
        )
        self._session = session
        self._result_task = asyncio.create_task(self._deliver_result(session))

    async def _stop_session(self) -> None:
        if self._result_task is not None and not self._result_task.done():
            self._result_task.cancel()
            await asyncio.gather(self._result_task, return_exceptions=True)
        self._result_task = None
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _deliver_result(self, session: SttSession) -> None:
        started = time.monotonic()
        try:
            try:
                text = await asyncio.wait_for(
                    asyncio.shield(session.result), self._settings.stt.max_utterance_s
                )
            except TimeoutError:
                _LOGGER.warning(
                    "No end of utterance after %s s, finalizing", self._settings.stt.max_utterance_s
                )
                session.finalize()
                try:
                    text = await asyncio.wait_for(session.result, FINALIZE_TIMEOUT_S)
                except TimeoutError:
                    text = session.text
        except SonioxError as err:
            _LOGGER.error("Soniox error: %s", err)
            self._session = None
            await session.close()
            await self.write_event(Error(text=str(err), code=err.error_type).event())
            return

        _LOGGER.info("Transcript in %.2f s (%d chars)", time.monotonic() - started, len(text))
        _LOGGER.debug("Transcript: %r", text)
        # Ignore the rest of the audio stream until the next transcription request.
        self._session = None
        await self.write_event(Transcript(text=text).event())
        await session.close()
