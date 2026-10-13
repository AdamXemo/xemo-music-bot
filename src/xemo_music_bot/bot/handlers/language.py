"""The language picker, opened from the welcome's language button or with `/language`."""

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.bot.handlers.start import welcome_text
from xemo_music_bot.bot.keyboards.language import (
    OpenPickerCallback,
    PickerOrigin,
    PickLanguageCallback,
    picker_keyboard,
    welcome_keyboard,
)
from xemo_music_bot.bot.locales import Texts, get_texts
from xemo_music_bot.core.services.language import LanguageService
from xemo_music_bot.db.models import User
from xemo_music_bot.db.repositories.users import UsersRepository


async def handle_language_command(message: Message, db_user: User, texts: Texts) -> None:
    """Send the picker as a new message.

    Args:
        message: The `/language` message.
        db_user: The sender's row, injected by ``AccessMiddleware``.
        texts: The user's catalog, injected by ``AccessMiddleware``.
    """
    keyboard = picker_keyboard(db_user.language, PickerOrigin.COMMAND)
    await message.answer(texts.language_prompt, reply_markup=keyboard)


async def handle_open_picker(callback: CallbackQuery, db_user: User, texts: Texts) -> None:
    """Edit the welcome into the picker, highlighting the language stored now.

    Args:
        callback: The tap on the welcome's language button.
        db_user: The sender's row, injected by ``AccessMiddleware``.
        texts: The user's catalog, injected by ``AccessMiddleware``.
    """
    await callback.answer()
    keyboard = picker_keyboard(db_user.language, PickerOrigin.WELCOME)
    await _edit_message(callback, texts.language_prompt, keyboard)


async def handle_pick_language(
    callback: CallbackQuery,
    callback_data: PickLanguageCallback,
    db_user: User,
    session: AsyncSession,
) -> None:
    """Store the picked language and edit the picker into a reply in that language.

    Picking the current language is handled like a change.

    Args:
        callback: The tap on a language button.
        callback_data: The parsed button data.
        db_user: The sender's row, injected by ``AccessMiddleware``.
        session: The update's session, injected by ``DbSessionMiddleware``.
    """
    # Answered first, so a failed save cannot leave the button spinning.
    await callback.answer()
    service = LanguageService(UsersRepository(session))
    user = await service.set_language(db_user.tg_id, callback_data.language)
    # The injected `texts` is the old language's catalog; the reply is in the new one.
    texts = get_texts(user.language)
    # An edit error other than "not modified" propagates and DbSessionMiddleware rolls the
    # save back; accepted until the Error UX item decides the handling.
    if callback_data.origin is PickerOrigin.WELCOME:
        await _edit_message(callback, welcome_text(texts), welcome_keyboard(texts))
    else:
        await _edit_message(callback, texts.language_set, None)


async def _edit_message(
    callback: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup | None
) -> None:
    """Edit the message under the tapped button; ``keyboard=None`` removes the buttons."""
    # A deleted message comes as InaccessibleMessage and cannot be edited; the tap is
    # already answered, so there is nothing left to do.
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as error:
        # A double tap repeats an edit that is already applied; Telegram rejects it, and
        # the message already shows what the user asked for.
        if "message is not modified" not in error.message:
            raise


def build_router() -> Router:
    """Create the language router (see ``start.build_router`` for why it is a factory)."""
    router = Router(name="language")
    router.message.register(handle_language_command, Command("language"))
    router.callback_query.register(handle_open_picker, OpenPickerCallback.filter())
    router.callback_query.register(handle_pick_language, PickLanguageCallback.filter())
    return router
