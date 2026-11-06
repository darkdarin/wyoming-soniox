"""Choosing the TTS model and voices: models API or the built-in list after a probe."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from wyoming_soniox.settings import TtsSettings
from wyoming_soniox.soniox_stt import SonioxError
from wyoming_soniox.soniox_tts import BUILTIN_VOICES, load_catalog

from .conftest import API_KEY, FakeSonioxTts

MODELS = {
    "models": [
        {
            "id": "tts-rt-v1",
            "languages": [{"code": "en", "name": "English"}],
            "voices": [{"id": "Old", "gender": "male", "description": "Old voice"}],
        },
        {
            "id": "tts-rt-v2",
            "languages": [{"code": "en", "name": "English"}, {"code": "ru", "name": "Russian"}],
            "voices": [
                {"id": "Maya", "gender": "female", "description": "Warm"},
                {"id": "Daniel", "gender": "male", "description": "Calm"},
                {"id": "Andrei", "gender": "male", "description": "A neutral Russian male voice"},
            ],
        },
    ]
}


@pytest.fixture
def models_api() -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server naming
            assert self.headers["Authorization"] == f"Bearer {API_KEY}"
            body = json.dumps(MODELS).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1/tts-models"
    server.shutdown()


NO_API = "http://127.0.0.1:9/v1/tts-models"  # nothing listens on the discard port


async def test_models_api_prefers_v2(models_api: str) -> None:
    catalog = await load_catalog(API_KEY, TtsSettings(models_url=models_api, language="en"))
    assert catalog.model == "tts-rt-v2"
    assert [v.id for v in catalog.voices] == ["Maya", "Daniel", "Andrei"]
    assert catalog.languages == ["en", "ru"]
    assert catalog.default_voice == "Maya"


async def test_default_voice_is_native_to_the_language(models_api: str) -> None:
    catalog = await load_catalog(API_KEY, TtsSettings(models_url=models_api, language="ru"))
    assert catalog.default_voice == "Andrei"


async def test_models_api_configured_voice(models_api: str) -> None:
    catalog = await load_catalog(API_KEY, TtsSettings(models_url=models_api, voice="Daniel"))
    assert catalog.default_voice == "Daniel"


async def test_builtin_voices_after_probe(soniox_tts: FakeSonioxTts) -> None:
    settings = TtsSettings(url=soniox_tts.url, models_url=NO_API, voice="Grace")
    catalog = await load_catalog(API_KEY, settings)

    assert catalog.model == "tts-rt-v2"
    assert catalog.voices == BUILTIN_VOICES
    assert "ru" in catalog.languages
    assert catalog.default_voice == "Grace"
    # The probe opened a stream and cancelled it without sending text.
    assert soniox_tts.configs[0]["voice"] == "Grace"
    assert soniox_tts.cancels == 1
    assert soniox_tts.texts == {"probe": ""}


async def test_probe_rejected(soniox_tts: FakeSonioxTts) -> None:
    soniox_tts.config_error_type = "permission_denied"
    with pytest.raises(SonioxError) as err:
        await load_catalog(API_KEY, TtsSettings(url=soniox_tts.url, models_url=NO_API))
    assert err.value.error_type == "permission_denied"
