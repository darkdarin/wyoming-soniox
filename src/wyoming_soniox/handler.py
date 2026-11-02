"""Wyoming event handler: one instance per client connection."""

import asyncio
import logging
import time

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler

from .settings import STT_LANGUAGES, Settings
from .soniox_stt import SonioxError, SttSession

_LOGGER = logging.getLogger(__name__)

FINALIZE_TIMEOUT_S = 5.0


class SonioxEventHandler(AsyncEventHandler):
    """Speech-to-text over Soniox; a client may run several transcriptions in a row."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        settings: Settings,
        info: Info,
    ) -> None:
        super().__init__(reader, writer)
        self._settings = settings
        self._info = info
        self._converter = AudioChunkConverter(rate=16000, width=2, channels=1)
        self._session: SttSession | None = None
        self._result_task: asyncio.Task | None = None

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self._info.event())
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
