"""The language picker's taps and `/language` (the first-run picker is sent by `/start`)."""

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.bot.commands import set_user_commands
from xemo_music_bot.bot.handlers.edits import edit_tapped_message
from xemo_music_bot.bot.handlers.start import welcome_text
from xemo_music_bot.bot.keyboards.language import (
    PickerOrigin,
    PickLanguageCallback,
    picker_keyboard,
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


async def handle_pick_language(
    callback: CallbackQuery,
    callback_data: PickLanguageCallback,
    db_user: User,
    session: AsyncSession,
    bot: Bot,
) -> None:
    """Store the picked language, edit the picker into a reply in it and update the menu.

    Picking the current language is handled like a change.

    Args:
        callback: The tap on a language button.
        callback_data: The parsed button data.
        db_user: The sender's row, injected by ``AccessMiddleware``.
        session: The update's session, injected by ``DbSessionMiddleware``.
        bot: The bot, injected by aiogram.
    """
    # Answered first, so a failed save cannot leave the button spinning.
    await callback.answer()
    service = LanguageService(UsersRepository(session))
    user = await service.set_language(db_user.tg_id, callback_data.language)
    # The injected `texts` is the old language's catalog; the reply is in the new one.
    texts = get_texts(user.language)
    # An edit error other than "not modified" propagates and DbSessionMiddleware rolls the
    # save back; accepted until the Error UX item decides the handling.
    if callback_data.origin is PickerOrigin.FIRST_RUN:
        await edit_tapped_message(callback, welcome_text(texts))
    else:
        await edit_tapped_message(callback, texts.language_set)
    # After the edit, so a failed edit (which rolls the pick back) leaves the menu alone.
    await set_user_commands(bot, user.tg_id, user.language)


def build_router() -> Router:
    """Create the language router (see ``start.build_router`` for why it is a factory)."""
    router = Router(name="language")
    router.message.register(handle_language_command, Command("language"))
    router.callback_query.register(handle_pick_language, PickLanguageCallback.filter())
    return router
