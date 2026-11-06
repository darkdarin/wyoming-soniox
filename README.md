# wyoming-soniox

[Wyoming protocol](https://github.com/OHF-Voice/wyoming) server for [Soniox](https://soniox.com) real-time
speech-to-text and text-to-speech. Gives Home Assistant Assist (or any Wyoming client) fast streaming speech
recognition and synthesis in 60+ languages: about $0.12 per hour of recognized audio and $0.70 per hour of
generated speech.

- **Speech-to-text.** Soniox detects the end of the utterance itself, so Home Assistant's own voice activity
  detection is not used (`requires_external_vad=False`): the transcript arrives right after you stop speaking.
- **Text-to-speech.** Streaming input: Home Assistant sends the assistant's answer while the LLM is still writing
  it, and audio starts before the answer is complete. Soniox voices speak every supported language; the server
  lists them for the voice picker in Home Assistant.

> Status: early development. The Home Assistant app works; publishing and a Docker image are coming.

## Run

```sh
export SONIOX_API_KEY=...   # https://console.soniox.com
uvx --from git+https://github.com/darkdarin/wyoming-soniox wyoming-soniox --uri tcp://0.0.0.0:10300
```

Then add the **Wyoming Protocol** integration in Home Assistant with this host and port 10300, and select
Soniox as speech-to-text and/or text-to-speech in your voice assistant.

The API key needs permission for both products (speech-to-text and text-to-speech) in the Soniox console.
Without text-to-speech permission the server keeps working as speech-to-text only and retries every 5 minutes;
reload the Wyoming integration in Home Assistant once text-to-speech becomes available.

## Options

| Option | Default | Description |
|---|---|---|
| `--api-key` | `$SONIOX_API_KEY` | Soniox API key |
| `--uri` | `tcp://0.0.0.0:10300` | `tcp://host:port` or `unix:///path` |
| `--model` | `stt-rt-v5` | Soniox real-time speech-to-text model |
| `--language` | `ru` | Speech-to-text language when the client sends no supported one |
| `--no-language-hints-strict` | | Allow languages other than the requested one |
| `--context-term` | | Domain term to improve recognition, repeatable |
| `--context-text` | | Free-form context |
| `--endpoint-latency-adjustment-level` | `2` | 0–3, higher ends utterances faster |
| `--endpoint-sensitivity` | `0.3` | -1.0…1.0 |
| `--max-endpoint-delay-ms` | `1500` | 500–3000 |
| `--wake-word` | | Cut this wake word (and anything before it) from the start of the transcript, for satellites that send audio including the wake word. Repeatable |
| `--wake-word-window-ms` | `3000` | Only look for the wake word among words starting this early |
| `--max-utterance-s` | `15` | Safety limit for one utterance |
| `--no-tts` | | Disable text-to-speech |
| `--tts-model` | first offered | Soniox text-to-speech model |
| `--tts-voice` | first offered | Voice used when the client does not request one |
| `--tts-language` | `ru` | Language of the synthesized speech (Wyoming clients send a voice, not a language) |
| `--tts-speed` | `1.0` | 0.7–1.3 |
| `--debug` | | Debug logging |
| `--debug-audio-dir` | | Save the audio of each speech-to-text session as WAV (debugging only) |

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## License

MIT
