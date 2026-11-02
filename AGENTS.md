# AGENTS.md

**wyoming-soniox** — Wyoming-сервер распознавания речи поверх облачного потокового STT [Soniox](https://soniox.com).
Любой Wyoming-клиент (в первую очередь Home Assistant Assist) получает быстрый потоковый STT для русского
и других языков почти бесплатно (~$0,12 за час звука). Конец фразы определяет Soniox, а не VAD Home Assistant.

Проект универсальный: не привязан к Яндекс Станции, рассчитан на переиспользование другими.
Родился из [ha-yandex-station](../ha-yandex-station) (интеграция рутованной Станции с HA), где ищем минимальную
задержку голосового ответа.

## Статус

MVP-сервер готов и проверен против настоящего Soniox; следующий — этап 2 (живая проверка с HA). Текущее состояние и следующий шаг — [docs/roadmap.md](docs/roadmap.md).

## Документация (читать перед работой)

- [docs/architecture.md](docs/architecture.md) — решения и устройство сервера
- [docs/ha-findings.md](docs/ha-findings.md) — что Home Assistant умеет и не умеет со STT (проверено по исходникам)
- [docs/soniox-api.md](docs/soniox-api.md) — WebSocket API Soniox: то, что нужно серверу
- [docs/stt-comparison.md](docs/stt-comparison.md) — почему Soniox: сравнение STT по цене и задержке
- [docs/roadmap.md](docs/roadmap.md) — этапы и открытые вопросы

## Компоненты

| Путь | Что |
|---|---|
| `src/wyoming_soniox/` | Python-пакет: Wyoming-сервер ↔ Soniox WebSocket (устройство — [architecture.md](docs/architecture.md)) |
| `tests/` | pytest, Soniox подменяется фейковым WebSocket-сервером |
| `scripts/transcribe.py` | ручная проверка: WAV → сервер в реальном темпе, печатает задержку |
| `scripts/ha_ws.py` | одна команда WebSocket API HA (пайплайны, `pipeline_debug`); токен из `main-ha.env` |
| `Dockerfile` | multi-arch образ (amd64, aarch64) в GHCR |
| `repository.yaml` + `wyoming_soniox_app/` | приложение (бывший add-on) для магазина Home Assistant |
| `.github/workflows/` | тесты, сборка образа, линт приложения |

## Рабочее окружение

| Что | Где / как |
|---|---|
| Home Assistant OS (RPi 5) | `ssh ha` (192.168.1.10, Terminal & SSH add-on), HA 2026.10.4. API-токен — `main-ha.env` в корне ha-yandex-station (gitignored, в чат не выводить) |
| Отладка Assist | WS `assist_pipeline/pipeline_debug/list|get` на HA; сейчас пайплайн «OpenAI» (облачный STT + агент) |
| Голосовой клиент для проверки | Яндекс Станция через ha-yandex-station (`ssh alice`) |
| GitHub | `git@github.com:darkdarin/wyoming-soniox.git`; push по SSH-ключу этого Mac, аккаунт `darkdarin`. `gh` авторизован под другим (рабочим) аккаунтом — для этого репозитория не годится |
| Soniox API-ключ | локально — `.env` в корне (`SONIOX_API_KEY=...`, gitignored, в чат не выводить); в HA — опция приложения `api_key` |

Команды: `uv run pytest`, `uv run ruff check . && uv run ruff format .`,
`uv run --env-file .env wyoming-soniox --uri tcp://127.0.0.1:10300 --debug`,
`uv run python scripts/transcribe.py speech.wav` (WAV 16 кГц моно; русская фраза — `say -v Milena -o x.aiff "…"` +
`afconvert -f WAVE -d LEI16@16000 -c 1 x.aiff x.wav`; файлы держать вне репозитория).

Ограничения: HA на Raspberry Pi 5 — тяжёлые локальные модели не предлагать.
Перезапуск HA касается живого дома: делать осознанно и сообщать.

## Правила

- Документация на русском; идентификаторы, код и комментарии в коде — на английском. README для внешних
  пользователей — на английском.
- Не коммитить API-ключи и записи звука из дома.
- Меняешь поведение протокола (Wyoming или Soniox) — обнови соответствующий документ в том же изменении.
- Пометки **[проверить]** снимать, только когда факт подтверждён (исходником, документацией или живым тестом).
