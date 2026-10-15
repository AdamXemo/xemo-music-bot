"""`/start`: the language picker until the user picks a language, then the welcome."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from xemo_music_bot.bot import emoji
from xemo_music_bot.bot.keyboards.language import PickerOrigin, picker_keyboard
from xemo_music_bot.bot.locales import Texts
from xemo_music_bot.db.models import User


def welcome_text(texts: Texts) -> str:
    """Return the welcome's message text, with the `hello` emoji slot in front."""
    return emoji.with_emoji(emoji.HELLO, texts.welcome)


async def handle_start(message: Message, db_user: User, texts: Texts) -> None:
    """Reply to `/start` with the first-run picker, or with the welcome after a pick.

    Args:
        message: The `/start` message.
        db_user: The sender's row, injected by ``AccessMiddleware``.
        texts: The user's catalog, injected by ``AccessMiddleware``.
    """
    if not db_user.language_chosen:
        keyboard = picker_keyboard(db_user.language, PickerOrigin.FIRST_RUN)
        await message.answer(texts.language_prompt, reply_markup=keyboard)
        return
    await message.answer(welcome_text(texts))


def build_router() -> Router:
    """Create the `/start` router.

    A router can be attached to only one dispatcher, so it is built per call rather than
    kept at module level; that lets tests build a fresh dispatcher each time.
    """
    router = Router(name="start")
    router.message.register(handle_start, CommandStart())
    return router
