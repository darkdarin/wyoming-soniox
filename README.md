# wyoming-soniox

[Wyoming protocol](https://github.com/OHF-Voice/wyoming) server for [Soniox](https://soniox.com) real-time
speech-to-text. Gives Home Assistant Assist (or any Wyoming client) fast streaming speech recognition in
60+ languages for about $0.12 per hour of audio.

Soniox detects the end of the utterance itself, so Home Assistant's own voice activity detection is not used
(`requires_external_vad=False`): the transcript arrives right after you stop speaking.

> Status: early development. Home Assistant app and Docker image are coming.

## Run

```sh
export SONIOX_API_KEY=...   # https://console.soniox.com
uvx --from git+https://github.com/darkdarin/wyoming-soniox wyoming-soniox --uri tcp://0.0.0.0:10300
```

Then add the **Wyoming Protocol** integration in Home Assistant with this host and port 10300, and select
Soniox as speech-to-text in your voice assistant.

## Options

| Option | Default | Description |
|---|---|---|
| `--api-key` | `$SONIOX_API_KEY` | Soniox API key |
| `--uri` | `tcp://0.0.0.0:10300` | `tcp://host:port` or `unix:///path` |
| `--model` | `stt-rt-v5` | Soniox real-time model |
| `--language` | `ru` | Used when the client sends no supported language |
| `--no-language-hints-strict` | | Allow languages other than the requested one |
| `--context-term` | | Domain term to improve recognition, repeatable |
| `--context-text` | | Free-form context |
| `--endpoint-latency-adjustment-level` | `2` | 0–3, higher ends utterances faster |
| `--endpoint-sensitivity` | `0.3` | -1.0…1.0 |
| `--max-endpoint-delay-ms` | `1500` | 500–3000 |
| `--max-utterance-s` | `15` | Safety limit for one utterance |
| `--debug` | | Debug logging |

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## License

MIT
