import html
import unicodedata
from dataclasses import fields

import pytest

from xemo_music_bot.bot.locales import DEFAULT_LANGUAGE, Texts, detect_language, get_texts
from xemo_music_bot.bot.locales.en import EN
from xemo_music_bot.bot.locales.ru import RU
from xemo_music_bot.bot.locales.uk import UK


@pytest.mark.parametrize(
    ("language_code", "expected"),
    [("en", "en"), ("uk", "uk"), ("ru", "ru"), ("en-US", "en"), ("UK", "uk"), ("ru-RU", "ru")],
)
def test_supported_language_codes_are_detected(language_code: str, expected: str) -> None:
    assert detect_language(language_code) == expected


@pytest.mark.parametrize("language_code", [None, "", "de", "pt-BR", "ukr"])
def test_missing_or_unsupported_language_falls_back_to_english(
    language_code: str | None,
) -> None:
    assert DEFAULT_LANGUAGE == "en"
    assert detect_language(language_code) == DEFAULT_LANGUAGE


def test_each_language_has_its_own_catalog() -> None:
    assert get_texts("en") is EN
    assert get_texts("uk") is UK
    assert get_texts("ru") is RU


@pytest.mark.parametrize("texts", [EN, UK, RU])
def test_language_button_fits_the_spec_budget(texts: Texts) -> None:
    assert len(texts.language_button) <= 20, texts.language_button


@pytest.mark.parametrize("texts", [EN, UK, RU])
def test_copy_is_valid_html_text(texts: Texts) -> None:
    # Copy is sent in HTML parse mode; a literal & or < breaks the send. Allow tags
    # explicitly when the spec asks for bold.
    for field in fields(texts):
        value = getattr(texts, field.name)
        assert html.escape(value, quote=False) == value, field.name


@pytest.mark.parametrize("texts", [EN, UK, RU])
def test_copy_contains_no_unicode_emoji(texts: Texts) -> None:
    # Owner rule: only premium custom emoji (sent as entities) may appear in bot copy.
    for field in fields(texts):
        value = getattr(texts, field.name)
        assert not [char for char in value if unicodedata.category(char) == "So"], field.name
