# Сравнение STT (исследование 2026-11-02)

Требования: минимальная задержка, потоковое распознавание, бесплатно или очень дёшево, хороший русский.
Профиль нагрузки владельца: ~50 команд в день по ~5 с ≈ 2 ч звука и ~1500 запросов в месяц — важно, как
сервис округляет короткие запросы.

## Облачные

| Сервис | Поток | Цена | ~2 ч / 1500 команд | Замечания |
|---|---|---|---|---|
| **Soniox** `stt-rt-v5` | WebSocket, текст по словам, свой endpoint detection | $0,12/ч | ≈ $0,25 | Подсказки языка и контекст. Готовой интеграции для HA нет — отсюда этот проект |
| Deepgram Nova-3 multilingual | WebSocket; по словам Soniox — результат по предложениям (не проверено) | ~$0,0058–0,009/мин, посекундно | ≈ $1; $200 кредита при регистрации | Запасной вариант |
| Azure Speech | да | 5 ч/мес бесплатно (F0) | 0 | Движок HA Cloud |
| Yandex SpeechKit | только gRPC (v3) | 0,16 ₽ за 15 с, остаток округляется вверх | ≈ 240 ₽ | Вероятно, лучший русский; gRPC — лишняя зависимость |
| Google Cloud | да, интеграция в ядре HA | V2 — $0,016/мин | ≈ $2 | Дорого без плюсов |
| OpenAI `gpt-4o-mini-transcribe` (Realtime) | WebSocket | ~$0,003/мин (неофициально) | ≈ $0,4 | Замечено: принимает русскую речь за английскую |

Независимых тестов качества русского не нашлось; WER на сайте Soniox — их маркетинг. Цифры цен частично со
сторонних агрегаторов — перед бюджетированием сверить с официальными страницами.

## Локальные (RPi 5)

- **T-one** (Т-Банк, 70M, Apache 2.0) — потоковый, русский, обучен на телефонии. Обёртки Wyoming нет.
- **GigaAM v3** (Сбер, ONNX через sherpa-onnx / `gigastt`) — лучшее открытое качество на русском, но не потоковый;
  скорость на Pi не измерена; у части весов некоммерческая лицензия.
- **Vosk** — потоковый, лёгкий, заметно хуже по качеству.

## Источники

- https://soniox.com/pricing, https://soniox.com/compare-stt/soniox-vs-deepgram/russian
- https://docs.soniox.com/stt/api-reference/websocket-api, …/stt/rt/endpoint-detection, …/stt/rt/manual-finalization
- https://convertaudiototext.com/blog/deepgram-nova-3-explained, https://agentdeals.dev/vendor/deepgram
- https://yandex.cloud/ru/docs/speechkit/pricing
- https://azure.microsoft.com/en-us/pricing/details/speech/
- https://www.costbench.com/software/ai-transcription-apis/google-speech-to-text/
- https://costgoat.com/pricing/openai-transcription
- https://huggingface.co/t-tech/T-one, https://github.com/ekhodzitsky/gigastt
- HACS: «There must only be one integration per repository» — https://www.hacs.xyz/docs/publish/integration/
