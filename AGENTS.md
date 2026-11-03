# AGENTS.md

**wyoming-soniox** — Wyoming-сервер распознавания речи поверх облачного потокового STT [Soniox](https://soniox.com).
Любой Wyoming-клиент (в первую очередь Home Assistant Assist) получает быстрый потоковый STT для русского
и других языков почти бесплатно (~$0,12 за час звука). Конец фразы определяет Soniox, а не VAD Home Assistant.

## Документация (читать перед работой)

Разработка и исследования — в Notion (workspace darkdarin), страница
[Wyoming Soniox](https://app.notion.com/p/40de74ee720f80a5978bda0daa32c897) и подстраницы:

- [Roadmap](https://app.notion.com/p/40de74ee720f81ee84a7d6cd3dd8c4ad) — текущее состояние и следующий шаг
- [Разработка: окружение и команды](https://app.notion.com/p/40de74ee720f8174ac5ee3400fc57ae5) — HA, ключи, команды,
  dev-установка приложения
- [Архитектура и решения](https://app.notion.com/p/40de74ee720f8148acc2c2866645de29) — поток запроса, настройки,
  устройство кода
- [Home Assistant и потоковый STT](https://app.notion.com/p/40de74ee720f81a09d51fbbc19d45d75),
  [Soniox real-time API](https://app.notion.com/p/40de74ee720f811199aceaebb4ea9868),
  [Выбор STT](https://app.notion.com/p/40de74ee720f8139899dede7a6a3a404),
  [Замеры на Станции](https://app.notion.com/p/40de74ee720f81a6bd72f2b8ae057a1e)

В репозитории — только документация для пользователей (английский): `README.md`, `wyoming_soniox_app/DOCS.md`,
`wyoming_soniox_app/translations/`.

## Компоненты

| Путь | Что |
|---|---|
| `src/wyoming_soniox/` | Python-пакет: Wyoming-сервер ↔ Soniox WebSocket |
| `tests/` | pytest, Soniox подменяется фейковым WebSocket-сервером |
| `scripts/` | ручные проверки: `transcribe.py` (WAV → сервер), `ha_ws.py` / `ha_runs.py` (HA API, `pipeline_debug`) |
| `repository.yaml` + `wyoming_soniox_app/` | приложение для магазина Home Assistant |

## Правила

- Документация разработки — в Notion, на русском; идентификаторы, код и комментарии в коде — на английском.
  Пользовательская документация в репозитории — на английском.
- Меняешь поведение протокола (Wyoming или Soniox) — обнови соответствующую страницу Notion в том же изменении.
- Пометки **[проверить]** снимать, только когда факт подтверждён (исходником, документацией или живым тестом).
- Не коммитить API-ключи и записи звука из дома. Ключи и токены (`.env`, `main-ha.env`, опции приложений)
  в чат не выводить.
- Перезапуск HA, переключение пайплайна и обновление приложений касаются живого дома: делать осознанно и сообщать.
