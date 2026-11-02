# Roadmap

## 0. Подготовка

- [x] Исследование STT, выбор Soniox, решения по архитектуре и репозиторию (2026-11-02)
- [x] Репозиторий `darkdarin/wyoming-soniox`; `git init`, первый коммит с документацией (2026-11-02)
- [x] API-ключ Soniox для живых тестов — в `.env` (2026-11-02)

## 1. MVP-сервер

- [x] `pyproject.toml` (uv), пакет `wyoming_soniox`, CLI: `--uri tcp://0.0.0.0:10300`, `--api-key`/env, опции
      из [architecture.md](architecture.md)
- [x] Wyoming: `describe` → `info` (`AsrProgram`, `requires_external_vad=False`, языки Soniox)
- [x] Сессия: `transcribe` → WS Soniox → чанки → `<end>` → `transcript`; `audio-stop` → `finalize` → `<fin>`
- [x] Таймауты, ошибки Soniox → Wyoming `error`, логи с `request_id`
- [x] Тесты с фейковым Soniox-сервером (endpoint, finalize, ошибка, обрыв, клиент закрыл раньше)
- [x] Живой прогон на Mac против настоящего Soniox через `scripts/transcribe.py` (2026-11-02, замеры —
      [soniox-api.md](soniox-api.md))

## 2. Живая проверка

- [x] Запустить локально на Mac, подключить к HA вручную (интеграция Wyoming → host:port), пайплайн с Soniox STT
      (2026-11-02: сервер на Mac `192.168.1.132:10300`, запись Wyoming «soniox» → `stt.soniox`; в пайплайне
      «OpenAI» STT заменён на `stt.soniox`, язык `ru`. Откат: `stt_engine: stt.openai_stt`, `stt_language: ru-RU`
      через `assist_pipeline/pipeline/update`)
- [x] Wake word в звуке (2026-11-02): Станция не присылает слово «Алиса», только иногда хвост «-са». Идея
      `send_wake_word` + `--wake-word` отброшена. Фиксированная обрезка 300 мс ломала быстрые команды, поэтому
      адаптер ha-yandex-station 0.2.5 режет хвост, только если за ним пауза. Сервер — без `--wake-word`
- [ ] Живая проверка адаптера 0.2.5 (обрезка хвоста) на колонке; записи — `--debug-audio-dir /tmp/wsx/audio`,
      после разбора удалить
- [x] Станция: замерить через `pipeline_debug` против пайплайна «OpenAI» (2026-11-02, [stt-benchmark.md](stt-benchmark.md):
      после конца речи 0,73 с против 1,43 с по медиане, точность наравне)
- [x] Начало звука (хвост wake word, потерянное начало быстрой команды) — задача адаптера, не STT: перенесено в
      roadmap yandex-quasar, раздел «Начало звука команды: wake word и SpotterEnd»
- [ ] Подобрать endpoint-параметры: не обрывает ли фразы на паузах («включи… свет на кухне»)
- [ ] Решить про `prefers_auto_gain_enabled` / `prefers_noise_reduction_enabled`

## 3. Поставка

- [ ] Dockerfile, multi-arch образ в GHCR
- [ ] Приложение HA: `repository.yaml`, `wyoming_soniox_app/` (`config.yaml` с опциями, Wyoming discovery через
      `bashio::discovery`, сборка на HA из локальных исходников или git-тега `v<version>`). 2026-11-02: собрано и
      установлено на HA как `local_wyoming_soniox`, ждёт API-ключ и переключения пайплайна
- [ ] CI: pytest, сборка образа по тегу, линт приложения
- [ ] README на английском: приложение / docker / pip, настройка пайплайна

## Потом

- Тёплое соединение / предварительное открытие сессии (взвесить цену)
- `transcript-chunk`, когда HA начнёт читать промежуточный текст
- Публикация в PyPI, анонс на community.home-assistant.io
- TTS Soniox (`wss://tts-rt.soniox.com/tts-websocket`) в том же сервере: `TtsProgram` в `info`, потоковый
  `synthesize-start/chunk/stop` от HA → текст в Soniox по мере генерации LLM → `audio-chunk`. Код с первого
  этапа раскладывать так, чтобы STT и TTS были отдельными обработчиками над общими настройками и клиентом
  [проверить: цена, русские голоса, модель вне preview]
