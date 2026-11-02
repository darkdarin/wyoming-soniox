# Home Assistant и потоковый STT: что проверено

Проверено по исходникам `home-assistant/core` 2026-11-02: теги `2026.10.4` (стоит у владельца), `2026.11.0b2` и
`main` (2026.12.0.dev0). Библиотека `wyoming==1.10.2` (её требует интеграция Wyoming в HA).

## Текст в conversation уходит только целиком

- `conversation.ConversationInput.text: str` — агент получает одну готовую строку, потокового ввода нет.
- Пайплайн (`assist_pipeline/default_pipeline.py`, `speech_to_text`) вызывает
  `internal_async_process_audio_stream` и ждёт **финальный** `SpeechResult`; этап intent начинается после него.
- С 2026.11 у STT-сущности есть `PartialSpeechResult` и `async_process_audio_stream_with_progress`
  (`stt/entity.py`): можно отдавать промежуточный текст. Но пайплайн даже в `main` их не потребляет — вызывает
  обёртку, которая возвращает только финальный результат.
- Протокол Wyoming умеет промежуточный текст (`transcript-start` / `transcript-chunk` / `transcript-stop`,
  флаг `AsrProgram.supports_transcript_streaming`), но клиент HA (`wyoming/stt.py`, `_async_receive_result`)
  читает только `transcript`.

Вывод: потоковость даёт выигрыш не за счёт «раннего» intent, а за счёт (1) мгновенного финального текста и
(2) определения конца фразы на стороне STT.

## STT может сам определять конец фразы

- `stt.SpeechAudioProcessing.requires_external_vad` — есть в 2026.10.4. Если `False`, пайплайн не создаёт
  `VoiceCommandSegmenter` (VAD HA) и отдаёт звук, пока STT не вернёт результат.
- Интеграция Wyoming берёт флаг из `info`: `requires_external_vad=asr_service.requires_external_vad`
  (`wyoming/stt.py`). В `wyoming.info.AsrProgram` поле `requires_external_vad: bool = True` по умолчанию.
- Клиент HA одновременно гонит две задачи: отправку звука и чтение ответа. Как только пришёл `transcript`,
  отправка отменяется (`asyncio.wait(..., FIRST_COMPLETED)`), поток звука закрывается.
- В `main` при таком режиме пайплайн после результата шлёт событие `STT_VAD_END`; в 2026.10.4 — нет.
  `STT_END` приходит в обоих случаях.
- Настройка пайплайна/сателлита «Определение конца речи» (silence_seconds) при этом режиме ни на что не влияет.
- Остальные флаги `AsrProgram`: `prefers_auto_gain_enabled`, `prefers_noise_reduction_enabled` (по умолчанию
  `True`) — влияют на обработку звука в HA. Для Soniox, вероятно, лучше `False` (сырой звук) [проверить на живых
  фразах].

## Что HA шлёт Wyoming-серверу

`wyoming/stt.py`, `async_process_audio_stream`:

1. `transcribe` с `language` из метаданных пайплайна (например `ru`). Остальные поля (`name`, `context`,
   `vad_sensitivity`) не заполняются.
2. `audio-start` — 16 000 Гц, 16 бит, моно.
3. `audio-chunk` × N по мере поступления.
4. `audio-stop`, если звук кончился раньше ответа (например, сателлит сам закрыл поток).

Ошибка/обрыв соединения → `SpeechResult(None, ERROR)`; `error`-событие от сервера логируется.

## Открытые вопросы

- Есть ли у пайплайна в 2026.10.4 своё ограничение длительности STT при `requires_external_vad=False`
  [проверить]. Пока считаем, что нет, — таймаут делаем в сервере.
- Discovery приложения: как официальные Wyoming-приложения объявляют себя HA (`discovery: [wyoming]` в
  `config.yaml` + сервис Supervisor) [проверить по addons-репозиторию OHF-Voice / home-assistant/addons].
