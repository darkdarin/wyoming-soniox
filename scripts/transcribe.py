"""Send a WAV file to a Wyoming ASR server in real time, like Home Assistant does.

Usage: uv run scripts/transcribe.py speech.wav [--uri tcp://127.0.0.1:10300] [--language ru]
The WAV must be 16 kHz, 16-bit, mono. Trailing silence is appended so endpoint detection can fire.
"""

import argparse
import asyncio
import time
import wave
from urllib.parse import urlparse

from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.error import Error

CHUNK_MS = 20


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wav")
    parser.add_argument("--uri", default="tcp://127.0.0.1:10300")
    parser.add_argument("--language", default="ru")
    parser.add_argument("--silence-s", type=float, default=3.0)
    args = parser.parse_args()

    with wave.open(args.wav, "rb") as wav:
        assert (wav.getframerate(), wav.getsampwidth(), wav.getnchannels()) == (16000, 2, 1)
        audio = wav.readframes(wav.getnframes())
    speech_end = len(audio) / 32000
    audio += b"\x00\x00" * int(16000 * args.silence_s)
    chunk_bytes = 32 * CHUNK_MS

    uri = urlparse(args.uri)
    async with AsyncTcpClient(uri.hostname, uri.port) as client:
        await client.write_event(Transcribe(language=args.language).event())
        await client.write_event(AudioStart(rate=16000, width=2, channels=1).event())
        started = time.monotonic()

        async def upload() -> None:
            for i in range(0, len(audio), chunk_bytes):
                chunk = AudioChunk(
                    rate=16000, width=2, channels=1, audio=audio[i : i + chunk_bytes]
                )
                await client.write_event(chunk.event())
                await asyncio.sleep(
                    max(0.0, started + (i + chunk_bytes) / 32000 - time.monotonic())
                )
            await client.write_event(AudioStop().event())

        upload_task = asyncio.create_task(upload())
        try:
            while (event := await client.read_event()) is not None:
                if Transcript.is_type(event.type) or Error.is_type(event.type):
                    break
        finally:
            upload_task.cancel()
        elapsed = time.monotonic() - started

    print(f"Event: {event.type if event else None} {event.data if event else ''}")
    print(f"Speech ended at {speech_end:.2f} s, result at {elapsed:.2f} s")
    print(f"Latency after end of speech: {elapsed - speech_end:.2f} s")


if __name__ == "__main__":
    asyncio.run(main())
