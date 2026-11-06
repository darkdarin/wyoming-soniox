# Changelog

Each version has two parts. **Server** is wyoming-soniox itself: it runs inside the Home Assistant app and in
the Docker image, and changes there affect every installation. **App** is the Home Assistant packaging: options,
installation, discovery. If a part did not change, it says so.

## 0.3.1

### Server

- **Text-to-speech no longer needs the Soniox models API.** Listing voices requires a separate key permission;
  without it the server now uses the built-in voice list after checking that the key may synthesize speech.
  Before, text-to-speech stayed unavailable even when the key could synthesize.
- The default voice is native to the speech language when Soniox offers one (Andrei for Russian) instead of the
  first voice in the list. Pick another one in the assistant's text-to-speech settings or with `tts_voice`.
- The default model is `tts-rt-v2`, the current Soniox text-to-speech model.

### App

No changes.

## 0.3.0

### Server

No changes.

### App

- **Installs from the app store as a ready-made image** (`ghcr.io/darkdarin/wyoming-soniox`) instead of being
  built on your Home Assistant: installing and updating take seconds and do not load a Raspberry Pi.
- Library versions in the image are pinned by `uv.lock`, so every installation runs the same code.
- New icon and logo.

## 0.2.1

### Server

- Fixed speech recognition failing ("Invalid data length") when a client splits audio into pieces of odd length,
  for example Home Assistant's speech-to-text API upload. Voice satellites were not affected.

### App

No changes.

## 0.2.0

### Server

- **Text-to-speech.** Soniox voices for Assist answers, in any of 60+ languages. With streaming input the answer is
  spoken while the assistant is still writing it. Voices are listed in the assistant's text-to-speech settings.
- Pauses in a streamed answer (for example, while an LLM calls a tool) no longer stop the speech.
- If the API key has no text-to-speech permission, speech-to-text keeps working and text-to-speech is retried
  every 5 minutes.

### App

- New options: default voice, speech language and speech speed.

## 0.1.0

### Server

- First version: streaming speech-to-text with Soniox over the Wyoming protocol. Soniox detects the end of the
  phrase, so the transcript is ready right after you stop speaking.

### App

- Home Assistant app with Wyoming discovery: Home Assistant finds it automatically.
