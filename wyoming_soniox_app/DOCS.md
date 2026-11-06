# Wyoming Soniox

Streaming speech-to-text and text-to-speech for Home Assistant Assist with [Soniox](https://soniox.com).

- **Speech-to-text:** Soniox detects the end of your phrase itself, so the transcript is ready right after you stop
  speaking — no waiting for Home Assistant's silence detection. About $0.12 per hour of audio.
- **Text-to-speech:** the answer is spoken while the assistant is still writing it. Every voice speaks every
  language. About $0.70 per hour of speech.

Russian and 60+ other languages.

## Setup

1. Create an API key at [console.soniox.com](https://console.soniox.com) with permission for speech-to-text and
   text-to-speech, and enter it in the app configuration.
2. Start the app. Home Assistant discovers it: confirm the **Wyoming Protocol** integration.
3. In **Settings → Voice assistants**, select **soniox** as speech-to-text and text-to-speech of your assistant,
   and pick a voice.

If the key has no text-to-speech permission, only speech-to-text is offered. After fixing the key, restart the
app and reload the Wyoming Soniox integration.

## Tuning

- **Context terms** — add names of your devices and rooms if they are recognized poorly.
- **End of speech speed / sensitivity / max delay** — lower values wait longer, so pauses inside a phrase do not
  cut it; higher values answer sooner.
- **Speech language** — the language voices speak in; Home Assistant does not pass it to the app.
