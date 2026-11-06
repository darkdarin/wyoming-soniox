"""End-to-end tests: Wyoming client -> wyoming-soniox -> fake Soniox."""

import asyncio
import json

import pytest
from websockets.asyncio.server import ServerConnection
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Describe, Info

from wyoming_soniox.settings import SttSettings

from .conftest import API_KEY, FakeSoniox, tokens

CHUNK = b"\x01\x00" * 1600  # 100 ms of 16 kHz mono s16le


async def start(client: AsyncTcpClient, language: str | None = "ru") -> None:
    await client.write_event(Transcribe(language=language).event())
    await client.write_event(AudioStart(rate=16000, width=2, channels=1).event())


async def send_chunks(client: AsyncTcpClient, count: int, rate: int = 16000) -> None:
    for _ in range(count):
        await client.write_event(AudioChunk(rate=rate, width=2, channels=1, audio=CHUNK).event())


async def read_result(client: AsyncTcpClient) -> Event:
    async with asyncio.timeout(5):
        while True:
            event = await client.read_event()
            assert event is not None, "connection closed"
            if Transcript.is_type(event.type) or Error.is_type(event.type):
                return event


async def test_describe(client: AsyncTcpClient) -> None:
    await client.write_event(Describe().event())
    event = await client.read_event()
    assert event is not None
    info = Info.from_event(event)
    assert len(info.asr) == 1
    asr = info.asr[0]
    assert asr.requires_external_vad is False
    assert asr.models[0].name == "stt-rt-v5"
    assert "ru" in asr.models[0].languages


async def test_endpoint_returns_transcript(client: AsyncTcpClient, soniox: FakeSoniox) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await fake.receive_until(ws, lambda _: len(fake.audio) >= 3 * len(CHUNK))
        await ws.send(tokens(("Вклю", False)))
        await ws.send(tokens(("Включи", True), (" свет", True), (" на", False)))
        await ws.send(tokens((" на кухне", True), ("<end>", True)))
        await fake.receive_until(ws, lambda _: False)

    soniox.behavior = behavior
    await start(client, language="ru-RU")
    await send_chunks(client, 3)

    event = await read_result(client)
    assert Transcript.from_event(event).text == "Включи свет на кухне"
    assert soniox.headers["authorization"] == f"Bearer {API_KEY}"
    assert soniox.config["language_hints"] == ["ru"]
    assert soniox.config["audio_format"] == "pcm_s16le"
    assert soniox.config["enable_endpoint_detection"] is True
    # The Soniox stream is closed right after the result.
    async with asyncio.timeout(5):
        await soniox.closed.wait()


async def test_audio_stop_finalizes(client: AsyncTcpClient, soniox: FakeSoniox) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await fake.receive_until(ws, lambda m: m == {"type": "finalize"})
        await ws.send(tokens(("Привет", True), ("<fin>", True)))
        await fake.receive_until(ws, lambda _: False)

    soniox.behavior = behavior
    await start(client)
    await send_chunks(client, 2)
    await client.write_event(AudioStop().event())

    event = await read_result(client)
    assert Transcript.from_event(event).text == "Привет"
    assert len(soniox.audio) == 2 * len(CHUNK)


async def test_soniox_error(client: AsyncTcpClient, soniox: FakeSoniox) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await ws.send(
            json.dumps(
                {
                    "tokens": [],
                    "error_code": 401,
                    "error_type": "unauthenticated",
                    "error_message": "Invalid API key",
                    "request_id": "req-1",
                }
            )
        )

    soniox.behavior = behavior
    await start(client)
    await send_chunks(client, 1)

    event = await read_result(client)
    error = Error.from_event(event)
    assert error.code == "unauthenticated"
    assert "req-1" in error.text


async def test_connection_closed_without_result(client: AsyncTcpClient, soniox: FakeSoniox) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await ws.close()

    soniox.behavior = behavior
    await start(client)

    event = await read_result(client)
    assert Error.is_type(event.type)


@pytest.fixture
def short_utterance(stt_settings: SttSettings) -> SttSettings:
    stt_settings.max_utterance_s = 0.3
    return stt_settings


@pytest.mark.usefixtures("short_utterance")
async def test_max_utterance_finalizes(client: AsyncTcpClient, soniox: FakeSoniox) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await fake.receive_until(ws, lambda m: m == {"type": "finalize"})
        await ws.send(tokens(("Долгая фраза", True), ("<fin>", True)))
        await fake.receive_until(ws, lambda _: False)

    soniox.behavior = behavior
    await start(client)
    await send_chunks(client, 1)

    event = await read_result(client)
    assert Transcript.from_event(event).text == "Долгая фраза"


async def test_finished_without_markers(client: AsyncTcpClient, soniox: FakeSoniox) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await ws.send(tokens(("Да", True)))
        await ws.send(json.dumps({"tokens": [], "finished": True}))

    soniox.behavior = behavior
    await start(client)

    event = await read_result(client)
    assert Transcript.from_event(event).text == "Да"


async def test_unsupported_language_falls_back(client: AsyncTcpClient, soniox: FakeSoniox) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await ws.send(tokens(("<end>", True)))
        await fake.receive_until(ws, lambda _: False)

    soniox.behavior = behavior
    await start(client, language="xx")

    event = await read_result(client)
    assert Transcript.from_event(event).text == ""
    assert soniox.config["language_hints"] == ["ru"]


async def test_audio_is_converted_to_16khz(client: AsyncTcpClient, soniox: FakeSoniox) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await fake.receive_until(ws, lambda m: m == {"type": "finalize"})
        await ws.send(tokens(("<fin>", True)))
        await fake.receive_until(ws, lambda _: False)

    soniox.behavior = behavior
    await start(client)
    await send_chunks(client, 2, rate=32000)
    await client.write_event(AudioStop().event())

    await read_result(client)
    assert abs(len(soniox.audio) - len(CHUNK)) <= 4


async def test_client_disconnect_closes_soniox(client: AsyncTcpClient, soniox: FakeSoniox) -> None:
    await start(client)
    await send_chunks(client, 1)
    async with asyncio.timeout(5):
        await soniox.audio_received.wait()
    await client.disconnect()

    async with asyncio.timeout(5):
        await soniox.closed.wait()


async def test_two_transcriptions_on_one_connection(
    client: AsyncTcpClient, soniox: FakeSoniox
) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await ws.send(tokens(("Раз", True), ("<end>", True)))
        await fake.receive_until(ws, lambda _: False)

    soniox.behavior = behavior
    for _ in range(2):
        await start(client)
        event = await read_result(client)
        assert Transcript.from_event(event).text == "Раз"


@pytest.fixture
def wake_word(stt_settings: SttSettings) -> SttSettings:
    stt_settings.wake_words = ["Алиса"]
    return stt_settings


@pytest.mark.usefixtures("wake_word")
async def test_endpoint_after_wake_word_keeps_listening(
    client: AsyncTcpClient, soniox: FakeSoniox
) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await ws.send(tokens(("Алиса", True), (".", True), ("<end>", True)))
        await ws.send(tokens((" Включи", True), (" свет.", True), ("<end>", True)))
        await fake.receive_until(ws, lambda _: False)

    soniox.behavior = behavior
    await start(client)

    event = await read_result(client)
    assert Transcript.from_event(event).text == "Включи свет."
    assert "Алиса" in soniox.config["context"]["terms"]


async def test_debug_audio_is_saved(
    stt_settings: SttSettings, tmp_path, client: AsyncTcpClient, soniox: FakeSoniox
) -> None:
    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        await fake.receive_until(ws, lambda m: m == {"type": "finalize"})
        await ws.send(tokens(("Да", True), ("<fin>", True)))
        await fake.receive_until(ws, lambda _: False)

    soniox.behavior = behavior
    stt_settings.debug_audio_dir = str(tmp_path)
    await start(client)
    await send_chunks(client, 2)
    await client.write_event(AudioStop().event())
    await read_result(client)
    await client.disconnect()  # Home Assistant disconnects right after the transcript

    async with asyncio.timeout(5):
        while not list(tmp_path.glob("*.wav")):  # noqa: ASYNC110 - waiting for a file
            await asyncio.sleep(0.01)
    [path] = tmp_path.glob("*.wav")
    assert path.stat().st_size == 44 + 2 * len(CHUNK)


async def test_odd_chunks_are_sent_as_whole_samples(
    client: AsyncTcpClient, soniox: FakeSoniox
) -> None:
    frames: list[int] = []

    async def behavior(fake: FakeSoniox, ws: ServerConnection) -> None:
        async def record(message: object) -> bool:
            if isinstance(message, bytes):
                frames.append(len(message))
            return message == {"type": "finalize"}

        while not await record(await fake.receive(ws)):
            pass
        await ws.send(tokens(("Да", True), ("<fin>", True)))
        await fake.receive_until(ws, lambda _: False)

    soniox.behavior = behavior
    await start(client)
    for size in (1717, 3, 2000):
        await client.write_event(
            AudioChunk(rate=16000, width=2, channels=1, audio=bytes(size)).event()
        )
    await client.write_event(AudioStop().event())

    await read_result(client)
    assert all(size % 2 == 0 for size in frames)
    assert sum(frames) == 3720
