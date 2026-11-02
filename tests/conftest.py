"""Fixtures: a fake Soniox WebSocket server and a running Wyoming server."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from websockets.asyncio.server import ServerConnection, serve
from wyoming.client import AsyncTcpClient

from wyoming_soniox.__main__ import build_info
from wyoming_soniox.handler import SonioxEventHandler
from wyoming_soniox.settings import Settings, SttSettings

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


@pytest.fixture
def stt_settings(soniox: FakeSoniox) -> SttSettings:
    return SttSettings(url=soniox.url)


@pytest.fixture
async def client(stt_settings: SttSettings) -> AsyncIterator[AsyncTcpClient]:
    settings = Settings(api_key=API_KEY, stt=stt_settings)
    info = build_info(settings)
    handlers: list[asyncio.Task] = []

    async def on_connect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        handler = SonioxEventHandler(reader, writer, settings=settings, info=info)
        handlers.append(asyncio.create_task(handler.run()))

    server = await asyncio.start_server(on_connect, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with AsyncTcpClient("127.0.0.1", port) as wyoming_client:
        yield wyoming_client
    server.close()
    await asyncio.gather(*handlers, return_exceptions=True)
