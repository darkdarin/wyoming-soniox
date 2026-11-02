# Wyoming Soniox

Streaming speech-to-text for Home Assistant Assist with [Soniox](https://soniox.com). Soniox detects the end of
your phrase itself, so the transcript is ready right after you stop speaking — no waiting for Home Assistant's
silence detection. Russian and 60+ other languages, about $0.12 per hour of audio.

## Setup

1. Create an API key at [console.soniox.com](https://console.soniox.com) and enter it in the app configuration.
2. Start the app. Home Assistant discovers it: confirm the **Wyoming Protocol** integration.
3. In **Settings → Voice assistants**, select **soniox** as speech-to-text of your assistant.

## Tuning

- **Context terms** — add names of your devices and rooms if they are recognized poorly.
- **End of speech speed / sensitivity / max delay** — lower values wait longer, so pauses inside a phrase do not
  cut it; higher values answer sooner.
