"""Unit tests for cutting the wake word from the transcript."""

import pytest

from wyoming_soniox.wake_word import Token, strip_wake_word


def tokens(*items: tuple[str, int]) -> list[Token]:
    return [Token(text, start_ms) for text, start_ms in items]


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        # Word pieces are joined into words before matching.
        (
            [("А", 900), ("ли", 1000), ("са", 1100), (",", 1200), (" вклю", 1500), ("чи", 1600)],
            "Включи",
        ),
        # Misrecognized endings still match.
        ([("Алис", 900), (" включи", 1500), (" свет", 1800)], "Включи свет"),
        ([("Алисе", 900), (".", 1100), (" Отмени", 1500), (" таймер.", 1800)], "Отмени таймер."),
        # Noise before the wake word is dropped too.
        ([("Да", 100), (" да", 400), (" Алиса", 900), (" стоп", 1500)], "Стоп"),
        # Only the first wake word is cut.
        ([("Алиса", 900), (" позови", 1500), (" Алису", 1900)], "Позови Алису"),
    ],
)
def test_strips_wake_word(items: list[tuple[str, int]], expected: str) -> None:
    assert strip_wake_word(tokens(*items), ["Алиса"], 3000) == (expected, True)


def test_no_wake_word_keeps_text() -> None:
    result = strip_wake_word(tokens(("Включи", 100), (" свет", 400)), ["Алиса"], 3000)
    assert result == ("Включи свет", False)


def test_wake_word_outside_window_is_kept() -> None:
    result = strip_wake_word(tokens(("Позови", 100), (" Алису", 3500)), ["Алиса"], 3000)
    assert result == ("Позови Алису", False)


def test_only_wake_word() -> None:
    assert strip_wake_word(tokens(("Алиса", 900), (".", 1200)), ["Алиса"], 3000) == ("", True)


def test_multi_word_wake_word() -> None:
    items = tokens(("Окей", 500), (",", 700), (" Яндекс", 800), (" стоп", 1500))
    assert strip_wake_word(items, ["Алиса", "Окей Яндекс"], 3000) == ("Стоп", True)
