<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/darkdarin/wyoming-soniox/main/assets/dark_logo.png">
    <img alt="Wyoming Soniox" src="https://raw.githubusercontent.com/darkdarin/wyoming-soniox/main/assets/logo.png" width="400">
  </picture>
</p>

# Wyoming Soniox

[![Release](https://img.shields.io/github/v/release/darkdarin/wyoming-soniox?sort=semver)](https://github.com/darkdarin/wyoming-soniox/releases)
[![CI](https://github.com/darkdarin/wyoming-soniox/actions/workflows/ci.yml/badge.svg)](https://github.com/darkdarin/wyoming-soniox/actions/workflows/ci.yml)
[![Validate](https://github.com/darkdarin/wyoming-soniox/actions/workflows/validate.yml/badge.svg)](https://github.com/darkdarin/wyoming-soniox/actions/workflows/validate.yml)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-18BCF2?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
![aarch64](https://img.shields.io/badge/aarch64-yes-green.svg)
![amd64](https://img.shields.io/badge/amd64-yes-green.svg)
[![License](https://img.shields.io/github/license/darkdarin/wyoming-soniox)](LICENSE)

Fast streaming **speech-to-text** and **text-to-speech** for Home Assistant Assist — or any
[Wyoming](https://github.com/OHF-Voice/wyoming) client — powered by the [Soniox](https://soniox.com) cloud.

> Unofficial project, not affiliated with Soniox. You need your own Soniox account and API key.

## Why

Most cloud speech-to-text services in Home Assistant receive the whole recording after Home Assistant has
waited for silence. Soniox listens to the stream and decides itself when you have finished the phrase, so the
transcript is ready right after you stop speaking. On a real voice satellite this halved the delay after the end
of speech compared with OpenAI speech-to-text: **0.73 s vs 1.43 s** (median of 12 commands).

## Features

- **Speech-to-text** without Home Assistant's silence detection (`requires_external_vad=False`): the end of the
  phrase is detected by Soniox from meaning and intonation, and is tunable.
- **Text-to-speech** with streaming input: Home Assistant sends the assistant's answer while the LLM is still
  writing it, and the speaker starts talking before the answer is complete.
- **60+ languages**, Russian included; every voice speaks every language. Voices show up in the voice picker of
  Home Assistant.
- **Cheap:** about $0.12 per hour of recognized audio and $0.70 per hour of generated speech, pay as you go.
- **Home Assistant app** with discovery, or a plain Docker image / Python package for any Wyoming client.

## Requirements

- A Soniox API key from [console.soniox.com](https://console.soniox.com) with permission for **speech-to-text**
  and, for spoken answers, **text-to-speech**.
- Home Assistant 2026.10 or newer with an Assist voice assistant (**Settings → Voice assistants**).

## Installation

### Home Assistant app (recommended)

[![Open the app in Home Assistant](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=89e90f00_wyoming_soniox&repository_url=https%3A%2F%2Fgithub.com%2Fdarkdarin%2Fwyoming-soniox)

1. Click the button above: Home Assistant offers to add this repository and opens the app page.
   Manually: **Settings → Apps → App store → ⋮ → Repositories**, add
   `https://github.com/darkdarin/wyoming-soniox`, then find **Wyoming Soniox** in the store.
2. Install the app, enter your Soniox API key on the **Configuration** tab and start it.
3. **Settings → Devices & services** shows the discovered **Wyoming Protocol** integration: click **Configure**.
4. **Settings → Voice assistants**, open your assistant, select **soniox** as speech-to-text and text-to-speech,
   and pick a voice.

### Docker

The app image runs anywhere, without Home Assistant's Supervisor:

```sh
docker run -d --name wyoming-soniox -p 10300:10300 -e SONIOX_API_KEY=your-key \
  ghcr.io/darkdarin/wyoming-soniox python3 -m wyoming_soniox --uri tcp://0.0.0.0:10300
```

Then add the **Wyoming Protocol** integration in Home Assistant with the host of the container and port `10300`.

### Python

```sh
export SONIOX_API_KEY=your-key
uvx --from git+https://github.com/darkdarin/wyoming-soniox wyoming-soniox --uri tcp://0.0.0.0:10300
```

## Configuration

App options are on its **Configuration** tab; the same settings are command-line options of the server.

| App option | Command line | Default | Description |
|---|---|---|---|
| `api_key` | `--api-key` | `$SONIOX_API_KEY` | Soniox API key |
| `language` | `--language` | `ru` | Speech-to-text language when the client sends none (Home Assistant sends the assistant's language) |
| `model` | `--model` | `stt-rt-v5` | Soniox real-time speech-to-text model |
| `language_hints_strict` | `--no-language-hints-strict` | on | Recognize only the requested language |
| `context_terms` | `--context-term` | | Names of devices, rooms and other words to recognize better (repeatable) |
| `context_text` | `--context-text` | | Free-form context for recognition |
| `endpoint_latency_adjustment_level` | same | `2` | 0–3: higher ends the phrase sooner after you stop speaking |
| `endpoint_sensitivity` | same | `0.3` | -1…1: higher detects the end of speech more eagerly |
| `max_endpoint_delay_ms` | same | `1500` | 500–3000: longest wait after speech before the phrase ends |
| `max_utterance_s` | same | `15` | Safety limit for one phrase |
| `tts_voice` | `--tts-voice` | first voice | Voice used when the assistant does not select one |
| `tts_language` | `--tts-language` | `ru` | Language of the synthesized speech (see below) |
| `tts_speed` | `--tts-speed` | `1.0` | 0.7–1.3 |
| `wake_words` | `--wake-word` | | Only for satellites that send audio including the wake word: cut it from the text |
| `debug_logging` | `--debug` | off | Verbose log |

Command line only: `--uri` (default `tcp://0.0.0.0:10300`), `--tts-model`, `--no-tts`,
`--wake-word-window-ms`, `--debug-audio-dir`.

**Speech language.** Home Assistant passes a voice name to Wyoming text-to-speech, but not the language, so the
server speaks in `tts_language`. Soniox voices speak every language with the same identity.

**Tuning the end of speech.** If a phrase is cut on a pause inside it ("turn on… the kitchen light"), lower the
end-of-speech speed or sensitivity, or raise the max delay. If short commands feel slow, do the opposite.

## Troubleshooting

- **No text-to-speech in Home Assistant.** The log says `Text-to-speech is unavailable … permission_denied`: allow
  text-to-speech for the key in the Soniox console. The server retries every 5 minutes; then reload the
  Wyoming Soniox integration so Home Assistant creates the text-to-speech entity.
- **Recognition errors.** Check the app log: Soniox errors are logged with their `request_id`. Assist debugging
  is under **Settings → Voice assistants → ⋮ → Debug**.

## How it works

```
Voice satellite ──audio──▶ Home Assistant Assist ──Wyoming──▶ wyoming-soniox ──WebSocket──▶ Soniox
                ◀─speech──                       ◀──────────                  ◀───────────
```

The server speaks the Wyoming protocol to Home Assistant and the Soniox real-time WebSocket APIs to the cloud:
audio is streamed to Soniox as it arrives and the transcript is returned at Soniox's end-of-phrase marker; for
text-to-speech, text is streamed in and audio is streamed back.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Releases, the local app build and notes for coding agents are in [AGENTS.md](AGENTS.md); changes are listed in
the [changelog](wyoming_soniox_app/CHANGELOG.md).

## License

[MIT](LICENSE)
