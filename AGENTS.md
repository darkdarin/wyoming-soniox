# AGENTS.md

**wyoming-soniox** is a Wyoming speech-to-text server on top of the [Soniox](https://soniox.com) cloud streaming STT.
Any Wyoming client (primarily Home Assistant Assist) gets fast streaming recognition for Russian and other languages
for almost nothing (~$0.12 per hour of audio). Soniox, not Home Assistant's VAD, decides when the phrase ends.

## Documentation (read before working)

Development notes and research live in Notion (workspace darkdarin; pages are in Russian), page
[Wyoming Soniox](https://app.notion.com/p/40de74ee720f80a5978bda0daa32c897) and its subpages:

- [Roadmap](https://app.notion.com/p/40de74ee720f81ee84a7d6cd3dd8c4ad) — current state and next step
- [Development: environment and commands](https://app.notion.com/p/40de74ee720f8174ac5ee3400fc57ae5) — Home Assistant
  access, keys, commands, dev install of the app
- [Architecture and decisions](https://app.notion.com/p/40de74ee720f8148acc2c2866645de29) — request flow, settings,
  code layout
- [Home Assistant and streaming STT](https://app.notion.com/p/40de74ee720f81a09d51fbbc19d45d75),
  [Soniox real-time API](https://app.notion.com/p/40de74ee720f811199aceaebb4ea9868),
  [Choosing an STT](https://app.notion.com/p/40de74ee720f8139899dede7a6a3a404),
  [Measurements on the Station](https://app.notion.com/p/40de74ee720f81a6bd72f2b8ae057a1e)

## Components

| Path | What |
|---|---|
| `src/wyoming_soniox/` | Python package: Wyoming server ↔ Soniox WebSocket |
| `tests/` | pytest; Soniox is replaced by a fake WebSocket server |
| `scripts/` | manual checks: `transcribe.py` (WAV → server), `ha_ws.py` / `ha_runs.py` (HA API, `pipeline_debug`) |
| `repository.yaml` + `wyoming_soniox_app/` | Home Assistant app for the app store |

## Rules

- Everything in the repository is in English: AGENTS.md, README, app docs and option translations, code comments,
  commit messages. Research and development notes go to the Notion pages above.
- When the protocol behaviour changes (Wyoming or Soniox), update the matching Notion page in the same change.
- Remove a **[проверить]** ("to verify") mark in Notion only once the fact is confirmed by source code,
  documentation or a live test.
- Never commit API keys or audio recorded at home. Never print keys and tokens (`.env`, `main-ha.env`, app options)
  in the chat.
- Restarting Home Assistant, switching the pipeline and updating apps affect a live home: do it deliberately and
  report it.
