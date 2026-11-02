"""Command line entry point."""

import argparse
import asyncio
import logging
import os
from functools import partial

from wyoming.info import AsrModel, AsrProgram, Attribution, Info
from wyoming.server import AsyncServer

from . import __version__
from .handler import SonioxEventHandler
from .settings import STT_LANGUAGES, Settings, SttSettings

_LOGGER = logging.getLogger(__name__)

SONIOX_ATTRIBUTION = Attribution(name="Soniox", url="https://soniox.com")


def build_info(settings: Settings) -> Info:
    """Describe the services this server provides."""
    return Info(
        asr=[
            AsrProgram(
                name="soniox",
                description="Soniox real-time speech-to-text",
                attribution=SONIOX_ATTRIBUTION,
                installed=True,
                version=__version__,
                models=[
                    AsrModel(
                        name=settings.stt.model,
                        description=f"Soniox {settings.stt.model}",
                        attribution=SONIOX_ATTRIBUTION,
                        installed=True,
                        version=None,
                        languages=STT_LANGUAGES,
                    )
                ],
                requires_external_vad=False,
            )
        ]
    )


def parse_args(argv: list[str] | None = None) -> Settings:
    """Build settings from command line arguments and environment."""
    defaults = SttSettings()
    parser = argparse.ArgumentParser(prog="wyoming-soniox", description=__doc__)
    parser.add_argument("--uri", default=Settings.uri, help="unix:// or tcp://")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("SONIOX_API_KEY"),
        help="Soniox API key (default: $SONIOX_API_KEY)",
    )
    parser.add_argument("--model", default=defaults.model)
    parser.add_argument(
        "--language",
        default=defaults.language,
        help="Language used when the client does not send a supported one",
    )
    parser.add_argument(
        "--no-language-hints-strict",
        dest="language_hints_strict",
        action="store_false",
        help="Allow Soniox to recognize languages other than the requested one",
    )
    parser.add_argument(
        "--context-term",
        dest="context_terms",
        action="append",
        default=[],
        help="Domain term to improve recognition (repeatable)",
    )
    parser.add_argument("--context-text", default="", help="Free-form context for recognition")
    parser.add_argument(
        "--endpoint-latency-adjustment-level",
        type=int,
        choices=range(4),
        default=defaults.endpoint_latency_adjustment_level,
    )
    parser.add_argument("--endpoint-sensitivity", type=float, default=defaults.endpoint_sensitivity)
    parser.add_argument("--max-endpoint-delay-ms", type=int, default=defaults.max_endpoint_delay_ms)
    parser.add_argument(
        "--wake-word",
        dest="wake_words",
        action="append",
        default=[],
        help="Wake word to cut from the start of the transcript, with anything before it; "
        "for satellites that send the audio including the wake word (repeatable)",
    )
    parser.add_argument(
        "--wake-word-window-ms",
        type=int,
        default=defaults.wake_word_window_ms,
        help="Only look for the wake word among words starting this early in the audio",
    )
    parser.add_argument("--max-utterance-s", type=float, default=defaults.max_utterance_s)
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    parser.add_argument(
        "--debug-audio-dir", default="", help="Save the audio of each session as WAV here"
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    if not args.api_key:
        parser.error("Soniox API key is required: --api-key or SONIOX_API_KEY")

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # websockets debug output includes request headers, i.e. the API key.
    logging.getLogger("websockets").setLevel(logging.WARNING)

    return Settings(
        api_key=args.api_key,
        uri=args.uri,
        stt=SttSettings(
            model=args.model,
            language=args.language,
            language_hints_strict=args.language_hints_strict,
            context_terms=args.context_terms,
            context_text=args.context_text,
            endpoint_latency_adjustment_level=args.endpoint_latency_adjustment_level,
            endpoint_sensitivity=args.endpoint_sensitivity,
            max_endpoint_delay_ms=args.max_endpoint_delay_ms,
            wake_words=args.wake_words,
            wake_word_window_ms=args.wake_word_window_ms,
            max_utterance_s=args.max_utterance_s,
            debug_audio_dir=args.debug_audio_dir,
        ),
    )


async def run(settings: Settings) -> None:
    """Run the Wyoming server until stopped."""
    info = build_info(settings)
    server = AsyncServer.from_uri(settings.uri)
    _LOGGER.info("Ready on %s (model %s)", settings.uri, settings.stt.model)
    await server.run(partial(SonioxEventHandler, settings=settings, info=info))


def main() -> None:
    settings = parse_args()
    try:
        asyncio.run(run(settings))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
