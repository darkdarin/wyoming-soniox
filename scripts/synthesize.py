"""Synthesize text through a Wyoming TTS server and save a WAV, like Home Assistant does.

Usage: uv run python scripts/synthesize.py "Text to speak" out.wav [--uri tcp://127.0.0.1:10300]
       [--voice Maya] [--stream]
With --stream the text is sent word by word (synthesize-start/chunk/stop), the way Home Assistant
streams an LLM answer; prints the time to the first audio.
"""

import argparse
import asyncio
import time
import wave
from urllib.parse import urlparse

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.client import AsyncTcpClient
from wyoming.error import Error
from wyoming.tts import (
    Synthesize,
    SynthesizeChunk,
    SynthesizeStart,
    SynthesizeStop,
    SynthesizeStopped,
    SynthesizeVoice,
)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("wav")
    parser.add_argument("--uri", default="tcp://127.0.0.1:10300")
    parser.add_argument("--voice")
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--word-delay-s", type=float, default=0.05, help="Between streamed words")
    args = parser.parse_args()

    voice = SynthesizeVoice(name=args.voice) if args.voice else None
    uri = urlparse(args.uri)
    audio = bytearray()
    rate = 0
    first_audio_s = None
    async with AsyncTcpClient(uri.hostname, uri.port) as client:
        started = time.monotonic()

        async def send() -> None:
            if not args.stream:
                await client.write_event(Synthesize(text=args.text, voice=voice).event())
                return
            await client.write_event(SynthesizeStart(voice=voice).event())
            for word in args.text.split(" "):
                await client.write_event(SynthesizeChunk(text=word + " ").event())
                await asyncio.sleep(args.word_delay_s)
            await client.write_event(Synthesize(text=args.text, voice=voice).event())
            await client.write_event(SynthesizeStop().event())

        sender = asyncio.create_task(send())
        end_type = SynthesizeStopped().event().type if args.stream else "audio-stop"
        while (event := await client.read_event()) is not None:
            if AudioStart.is_type(event.type):
                rate = AudioStart.from_event(event).rate
            elif AudioChunk.is_type(event.type):
                if first_audio_s is None:
                    first_audio_s = time.monotonic() - started
                audio += AudioChunk.from_event(event).audio
            elif Error.is_type(event.type):
                raise SystemExit(f"Error: {Error.from_event(event).text}")
            if event.type == end_type or (not args.stream and AudioStop.is_type(event.type)):
                break
        await sender
        total_s = time.monotonic() - started

    with wave.open(args.wav, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(audio))
    first = f"{first_audio_s:.2f}" if first_audio_s is not None else "-"
    print(f"{len(audio) / (rate * 2):.2f} s of audio at {rate} Hz; first audio after {first} s,")
    print(f"done after {total_s:.2f} s")


if __name__ == "__main__":
    asyncio.run(main())
