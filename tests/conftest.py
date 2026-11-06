"""Fixtures: a fake Soniox WebSocket server and a running Wyoming server."""

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from websockets.asyncio.server import ServerConnection, serve
from wyoming.client import AsyncTcpClient

from wyoming_soniox.__main__ import build_info
from wyoming_soniox.handler import SonioxEventHandler
from wyoming_soniox.settings import Settings, SttSettings, TtsSettings
from wyoming_soniox.soniox_tts import TtsCatalog, TtsVoiceInfo

API_KEY = "test-key"


@dataclass
class FakeSoniox:
    """Records what the server received; `behavior` scripts the replies."""

    behavior: Callable[["FakeSoniox", ServerConnection], Awaitable[None]] | None = None
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    audio: bytearray = field(default_factory=bytearray)
    controls: list[dict[str, Any]] = field(default_factory=list)
    audio_received: asyncio.Event = field(default_factory=asyncio.Event)
    closed: asyncio.Event = field(default_factory=asyncio.Event)

    async def receive(self, ws: ServerConnection) -> Any:
        """Receive one message, recording it. Returns bytes, a control dict or '' (end)."""
        message = await ws.recv()
        if isinstance(message, bytes):
            self.audio.extend(message)
            self.audio_received.set()
            return message
        if message == "":
            return ""
        data = json.loads(message)
        self.controls.append(data)
        return data

    async def receive_until(self, ws: ServerConnection, predicate: Callable[[Any], bool]) -> None:
        while not predicate(await self.receive(ws)):
            pass

    async def handle(self, ws: ServerConnection) -> None:
        self.headers = dict(ws.request.headers)
        self.config = json.loads(await ws.recv())
        try:
            if self.behavior is not None:
                await self.behavior(self, ws)
            else:
                while True:
                    await self.receive(ws)
        except Exception:  # noqa: BLE001 - client went away
            pass
        finally:
            self.closed.set()


def tokens(*items: tuple[str, bool]) -> str:
    return json.dumps({"tokens": [{"text": text, "is_final": final} for text, final in items]})


@pytest.fixture
async def soniox() -> AsyncIterator[FakeSoniox]:
    fake = FakeSoniox()
    async with serve(fake.handle, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        fake.url = f"ws://127.0.0.1:{port}"
        yield fake


def tts_audio(text: str) -> bytes:
    """Audio the fake TTS server returns for a text: its UTF-8 bytes, padded to whole samples."""
    audio = text.encode()
    return audio + b"\0" * (len(audio) % 2)


@dataclass
class FakeSonioxTts:
    """Fake Soniox TTS: on `text_end` returns `tts_audio(text)` of the stream in two chunks.

    `timeout_after_text` makes the first stream end with `request_timeout` after its first text.
    """

    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    configs: list[dict[str, Any]] = field(default_factory=list)
    texts: dict[str, str] = field(default_factory=dict)
    connections: int = 0
    timeout_after_text: bool = False
    error_type: str = ""

    async def handle(self, ws: ServerConnection) -> None:
        self.connections += 1
        self.headers = dict(ws.request.headers)
        try:
            async for message in ws:
                data = json.loads(message)
                stream_id = data["stream_id"]
                if "voice" in data:
                    self.configs.append(data)
                    self.texts[stream_id] = ""
                    continue
                if data.get("cancel"):
                    await ws.send(json.dumps({"stream_id": stream_id, "terminated": True}))
                    continue
                self.texts[stream_id] += data.get("text", "")
                if self.error_type:
                    await self._send_error(ws, stream_id, self.error_type)
                elif self.timeout_after_text:
                    self.timeout_after_text = False
                    await self._send_audio(ws, stream_id)
                    await self._send_error(ws, stream_id, "request_timeout")
                elif data.get("text_end"):
                    await self._send_audio(ws, stream_id)
                    await ws.send(json.dumps({"stream_id": stream_id, "terminated": True}))
        except Exception:  # noqa: BLE001 - client went away
            pass

    async def _send_audio(self, ws: ServerConnection, stream_id: str) -> None:
        audio = tts_audio(self.texts[stream_id])
        half = len(audio) // 2
        for part, end in ((audio[:half], False), (audio[half:], True)):
            message = {"stream_id": stream_id, "audio": base64.b64encode(part).decode()}
            await ws.send(json.dumps(message | {"audio_end": end}))

    async def _send_error(self, ws: ServerConnection, stream_id: str, error_type: str) -> None:
        error = {"stream_id": stream_id, "error_code": 400, "error_type": error_type}
        await ws.send(json.dumps(error | {"error_message": "test", "request_id": "req-tts"}))
        await ws.send(json.dumps({"stream_id": stream_id, "terminated": True}))


@pytest.fixture
async def soniox_tts() -> AsyncIterator[FakeSonioxTts]:
    fake = FakeSonioxTts()
    async with serve(fake.handle, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        fake.url = f"ws://127.0.0.1:{port}"
        yield fake


@pytest.fixture
def stt_settings(soniox: FakeSoniox) -> SttSettings:
    return SttSettings(url=soniox.url)


@pytest.fixture
def tts_settings(soniox_tts: FakeSonioxTts) -> TtsSettings:
    return TtsSettings(url=soniox_tts.url, language="ru")


@pytest.fixture
def catalog() -> TtsCatalog:
    return TtsCatalog(
        model="tts-test",
        languages=["en", "ru"],
        voices=[TtsVoiceInfo("Maya", "female", "Warm"), TtsVoiceInfo("Daniel", "male", "Calm")],
        default_voice="Maya",
    )


@pytest.fixture
async def client(
    stt_settings: SttSettings, tts_settings: TtsSettings, catalog: TtsCatalog
) -> AsyncIterator[AsyncTcpClient]:
    settings = Settings(api_key=API_KEY, stt=stt_settings, tts=tts_settings)
    handlers: list[asyncio.Task] = []

    async def on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        handler = SonioxEventHandler(
            reader,
            writer,
            settings=settings,
            info=lambda: build_info(settings, catalog),
            catalog=catalog,
        )
        handlers.append(asyncio.create_task(handler.run()))

    server = await asyncio.start_server(on_connect, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with AsyncTcpClient("127.0.0.1", port) as wyoming_client:
        yield wyoming_client
    server.close()
    await asyncio.gather(*handlers, return_exceptions=True)
