"""The welcome's language button and the language picker, with their callback data."""

from enum import StrEnum

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from xemo_music_bot.bot import emoji
from xemo_music_bot.bot.locales import LANGUAGES, Language, Texts, get_texts


class PickerOrigin(StrEnum):
    """Where the picker was opened, which decides what a pick turns the message into."""

    WELCOME = "welcome"
    COMMAND = "command"


class OpenPickerCallback(CallbackData, prefix="language_picker"):
    """The welcome's language button: edits the welcome into the picker."""


class PickLanguageCallback(CallbackData, prefix="language"):
    """A language button in the picker.

    Stateless on purpose, so the buttons keep working on any old message. ``language`` is
    validated when the data is parsed: a forged value does not match the handler and never
    reaches the database.

    Attributes:
        language: The picked language.
        origin: Where the picker was opened.
    """

    language: Language
    origin: PickerOrigin


def welcome_keyboard(texts: Texts) -> InlineKeyboardMarkup:
    """Return the welcome's one full-width button that opens the picker.

    Args:
        texts: The user's catalog; the button names the current language in it.
    """
    button = InlineKeyboardButton(
        text=texts.language_button,
        icon_custom_emoji_id=emoji.icon_id(emoji.LANGUAGE),
        callback_data=OpenPickerCallback().pack(),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def picker_keyboard(current: Language, origin: PickerOrigin) -> InlineKeyboardMarkup:
    """Return one row with every language, each named in its own language.

    Args:
        current: The user's stored language, highlighted with ``style: primary``.
        origin: Where the picker is shown, carried in each button's callback data.
    """
    row = [
        InlineKeyboardButton(
            text=get_texts(language).language_name,
            style="primary" if language == current else None,
            callback_data=PickLanguageCallback(language=language, origin=origin).pack(),
        )
        for language in LANGUAGES
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row])
