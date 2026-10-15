"""The language picker and its callback data."""

from enum import StrEnum

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from xemo_music_bot.bot.locales import LANGUAGES, Language, get_texts


class PickerOrigin(StrEnum):
    """Which command sent the picker, which decides what a pick turns the message into.

    Attributes:
        FIRST_RUN: `/start` before the user's first pick; a pick turns it into the welcome.
        COMMAND: `/language`; a pick turns it into the ``language_set`` line.
    """

    FIRST_RUN = "first_run"
    COMMAND = "command"


class PickLanguageCallback(CallbackData, prefix="language"):
    """A language button in the picker.

    Stateless on purpose, so the buttons keep working on any old message. ``language`` is
    validated when the data is parsed: a forged value does not match the handler and never
    reaches the database.

    Attributes:
        language: The picked language.
        origin: Which command sent the picker.
    """

    language: Language
    origin: PickerOrigin


def picker_keyboard(current: Language, origin: PickerOrigin) -> InlineKeyboardMarkup:
    """Return one row with every language: its flag and its name in its own language.

    Args:
        current: The user's stored language, highlighted with ``style: primary``.
        origin: Which command sends the picker, carried in each button's callback data.
    """
    row = []
    for language in LANGUAGES:
        texts = get_texts(language)
        button = InlineKeyboardButton(
            text=f"{texts.language_flag} {texts.language_name}",
            style="primary" if language == current else None,
            callback_data=PickLanguageCallback(language=language, origin=origin).pack(),
        )
        row.append(button)
    return InlineKeyboardMarkup(inline_keyboard=[row])
