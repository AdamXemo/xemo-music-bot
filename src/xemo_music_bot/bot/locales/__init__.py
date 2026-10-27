"""User-facing copy in English, Ukrainian and Russian (ADR 0005).

Handlers never contain literal copy; they pick a `Texts` catalog here and read its fields.
"""

from typing import Final

from xemo_music_bot.bot.locales.catalog import Texts
from xemo_music_bot.bot.locales.en import EN
from xemo_music_bot.bot.locales.plural import Plural, plural
from xemo_music_bot.bot.locales.ru import RU
from xemo_music_bot.bot.locales.uk import UK
from xemo_music_bot.core.models import DEFAULT_LANGUAGE, Language

__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "Language",
    "Plural",
    "Texts",
    "detect_language",
    "get_texts",
    "plural",
]

_CATALOGS: Final[dict[Language, Texts]] = {"en": EN, "uk": UK, "ru": RU}

LANGUAGES: Final[tuple[Language, ...]] = tuple(_CATALOGS)
"""Every supported language, in the order the language picker shows them."""


def detect_language(language_code: str | None) -> Language:
    """Map Telegram's `language_code` to a supported language.

    Args:
        language_code: IETF tag from the Telegram user, such as `uk` or `en-US`.
            Telegram omits it for some clients.

    Returns:
        The matching language, or `DEFAULT_LANGUAGE` if the code is missing or unsupported.
    """
    if not language_code:
        return DEFAULT_LANGUAGE
    # Only the primary subtag matters: `en-GB` and `en-US` share one catalog.
    primary = language_code.split("-", maxsplit=1)[0].lower()
    # Matching against the keys narrows `str` to `Language` without a cast.
    for language in _CATALOGS:
        if language == primary:
            return language
    return DEFAULT_LANGUAGE


def get_texts(language: Language) -> Texts:
    """Return the catalog for ``language``."""
    return _CATALOGS[language]
