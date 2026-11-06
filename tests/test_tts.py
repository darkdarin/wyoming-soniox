"""End-to-end text-to-speech tests: Wyoming client -> wyoming-soniox -> fake Soniox TTS."""

import asyncio

import pytest
from wyoming.audio import AudioChunk, AudioStart
from wyoming.client import AsyncTcpClient
from wyoming.error import Error
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeVoice,
)

from wyoming_soniox.soniox_tts import TtsCatalog

from .conftest import API_KEY, FakeSonioxTts, tts_audio


async def read_until(client: AsyncTcpClient, *types: str) -> list[Event]:
    """Read events up to and including the first one of the given types."""
    events = []
    async with asyncio.timeout(5):
        while True:
            event = await client.read_event()
            assert event is not None, "connection closed"
            events.append(event)
            if event.type in types:
                return events


def audio_of(events: list[Event]) -> bytes:
    return b"".join(AudioChunk.from_event(e).audio for e in events if AudioChunk.is_type(e.type))


async def stream(
    client: AsyncTcpClient, pieces: list[str], voice: str | None = None, pause_s: float = 0.0
) -> None:
    """Send text the way Home Assistant streams LLM output."""
    synth_voice = SynthesizeVoice(name=voice) if voice else None
    await client.write_event(SynthesizeStart(voice=synth_voice).event())
    for piece in pieces:
        await client.write_event(SynthesizeChunk(text=piece).event())
        await asyncio.sleep(pause_s)
    await client.write_event(Synthesize(text="".join(pieces), voice=synth_voice).event())
    await client.write_event(SynthesizeStop().event())


async def test_describe_lists_voices(client: AsyncTcpClient) -> None:
    await client.write_event(Describe().event())
    event = await client.read_event()
    assert event is not None
    [tts] = Info.from_event(event).tts
    assert tts.supports_synthesize_streaming is True
    assert [voice.name for voice in tts.voices] == ["Maya", "Daniel"]
    assert tts.voices[0].languages == ["en", "ru"]
    assert tts.voices[0].description == "Maya — Warm"


async def test_synthesize(client: AsyncTcpClient, soniox_tts: FakeSonioxTts) -> None:
    await client.write_event(Synthesize(text="Привет, мир").event())
    events = await read_until(client, "audio-stop")

    assert AudioStart.is_type(events[0].type)
    start = AudioStart.from_event(events[0])
    assert (start.rate, start.width, start.channels) == (24000, 2, 1)
    assert audio_of(events) == tts_audio("Привет, мир")
    assert soniox_tts.headers["authorization"] == f"Bearer {API_KEY}"
    [config] = soniox_tts.configs
    assert config["model"] == "tts-test"
    assert config["voice"] == "Maya"
    assert config["language"] == "ru"
    assert config["audio_format"] == "pcm_s16le"


async def test_synthesize_with_voice(client: AsyncTcpClient, soniox_tts: FakeSonioxTts) -> None:
    await client.write_event(Synthesize(text="Да", voice=SynthesizeVoice(name="Daniel")).event())
    await read_until(client, "audio-stop")
    assert soniox_tts.configs[0]["voice"] == "Daniel"


async def test_unknown_voice_falls_back(client: AsyncTcpClient, soniox_tts: FakeSonioxTts) -> None:
    await client.write_event(Synthesize(text="Да", voice=SynthesizeVoice(name="Nobody")).event())
    await read_until(client, "audio-stop")
    assert soniox_tts.configs[0]["voice"] == "Maya"


async def test_streaming(client: AsyncTcpClient, soniox_tts: FakeSonioxTts) -> None:
    pieces = ["Свет ", "в гостиной ", "включён."]
    await stream(client, pieces, voice="Daniel")
    events = await read_until(client, "synthesize-stopped")

    types = [event.type for event in events]
    assert types[0] == "audio-start"
    assert types[-2:] == ["audio-stop", "synthesize-stopped"]
    assert audio_of(events) == tts_audio("".join(pieces))
    # The trailing full-text synthesize event is ignored: one Soniox stream only.
    assert len(soniox_tts.configs) == 1
    assert soniox_tts.configs[0]["voice"] == "Daniel"


async def test_streaming_survives_text_pause(
    client: AsyncTcpClient, soniox_tts: FakeSonioxTts
) -> None:
    soniox_tts.timeout_after_text = True
    # Soniox times the stream out after a few seconds without text; here the fake does it at once.
    await stream(client, ["Первая часть. ", "Вторая часть."], pause_s=0.2)
    events = await read_until(client, "synthesize-stopped")

    # The second piece of text went to a new stream after request_timeout.
    assert len(soniox_tts.configs) == 2
    assert audio_of(events) == tts_audio("Первая часть. ") + tts_audio("Вторая часть.")


async def test_two_requests_on_one_connection(
    client: AsyncTcpClient, soniox_tts: FakeSonioxTts
) -> None:
    await stream(client, ["Раз."])
    await read_until(client, "synthesize-stopped")
    await client.write_event(Synthesize(text="Два.").event())
    events = await read_until(client, "audio-stop")
    assert audio_of(events) == tts_audio("Два.")


async def test_soniox_error(client: AsyncTcpClient, soniox_tts: FakeSonioxTts) -> None:
    soniox_tts.error_type = "invalid_request"
    await client.write_event(Synthesize(text="Ошибка").event())
    [*_, event] = await read_until(client, "error")
    error = Error.from_event(event)
    assert error.code == "invalid_request"
    assert "req-tts" in error.text


async def test_streaming_error_ignores_trailing_synthesize(
    client: AsyncTcpClient, soniox_tts: FakeSonioxTts
) -> None:
    soniox_tts.error_type = "invalid_request"
    await stream(client, ["Ошибка."])
    await read_until(client, "error")
    soniox_tts.error_type = ""
    # After the error, the trailing synthesize must not start a second synthesis.
    await client.write_event(Synthesize(text="Потом").event())
    await read_until(client, "audio-stop")
    assert len(soniox_tts.configs) == 2
    assert soniox_tts.texts[soniox_tts.configs[-1]["stream_id"]] == "Потом"


@pytest.fixture
def empty_catalog(catalog: TtsCatalog) -> TtsCatalog:
    catalog.voices = []
    return catalog


@pytest.mark.usefixtures("empty_catalog")
async def test_unavailable_without_catalog(client: AsyncTcpClient) -> None:
    await client.write_event(Describe().event())
    event = await client.read_event()
    assert event is not None
    assert Info.from_event(event).tts == []

    await client.write_event(Synthesize(text="Привет").event())
    [*_, event] = await read_until(client, "error")
    assert Error.from_event(event).code == "tts_unavailable"
