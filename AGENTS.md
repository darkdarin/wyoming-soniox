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

## Repository and releases

- GitHub: `git@github.com:darkdarin/wyoming-soniox.git` (push over the SSH key of this Mac, account `darkdarin`).
  The globally active `gh` account is a work one; use the `darkdarin` token from the sibling project:
  `cd ../ha-yandex-station && direnv exec . gh … -R darkdarin/wyoming-soniox` (e.g. `run list`, `run watch`).
- The published app is a prebuilt image `ghcr.io/darkdarin/wyoming-soniox:<version>` (`image:` in
  `wyoming_soniox_app/config.yaml`); `.github/workflows/release.yml` builds it (amd64 and arm64) and publishes it.
  The same image serves Docker users (`python3 -m wyoming_soniox …` instead of the app's `run.sh`).
- **Every new version ships as a GitHub release with a changelog entry.** Bump the version in
  `wyoming_soniox_app/config.yaml` and `pyproject.toml`, run `uv lock`, add a `## <version>` section to
  `wyoming_soniox_app/CHANGELOG.md`, commit, tag `v<version>`, push the branch and the tag together. The release
  workflow fails without the section or on a version mismatch. The changelog is for users (what changed in use,
  not which files): Home Assistant shows it on the app's changelog tab.
- A version section has `### Server` (wyoming-soniox itself: the app, Docker, pip) and `### App` (Home Assistant
  packaging: options, installation, discovery); a part without changes says "No changes."
- Never push a bumped version to `main` without its tag in the same push: the app store would offer a version whose
  image does not exist yet, and the update fails. Releases and updates of the live Home Assistant only with the
  owner's consent.
- CI: `ci.yml` (ruff, pytest, trial amd64 image build and a run outside Home Assistant), `validate.yml` (app lint),
  `release.yml` (image and release on a tag).

### Local app build

`wyoming_soniox_app/build.sh` assembles the build context (app files + package source) in
`wyoming_soniox_app/.build/wyoming_soniox`. CI builds the image from it; copied to `/local_apps` on Home Assistant
it is a local app built by the Supervisor (its `config.yaml` has no `image:`). The Dockerfile installs
dependencies strictly from `uv.lock`, from PyPI only. Commands are on the Notion page "Development".

The live Home Assistant runs the store app `89e90f00_wyoming_soniox` (hostname `89e90f00-wyoming-soniox`); the
FlowPilot pipeline of the Station reaches it by the `uri` in its graph, so a hostname change breaks the Station's
voice. `scripts/ha_ws.py` uses the standard library only: run it with `/usr/bin/python3`
(`uv run --no-project --python /usr/bin/python3 --env-file ../ha-yandex-station/main-ha.env python scripts/ha_ws.py …`)
— macOS may block other interpreters from the local network.

Icons: `scripts/draw_logos.py` renders `wyoming_soniox_app/icon.png`, `logo.png` and `assets/*logo.png`.

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
