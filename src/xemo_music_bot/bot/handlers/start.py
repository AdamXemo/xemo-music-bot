"""`/start`: the welcome, in the user's language, with the language button."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from xemo_music_bot.bot import emoji
from xemo_music_bot.bot.keyboards.language import welcome_keyboard
from xemo_music_bot.bot.locales import Texts


def welcome_text(texts: Texts) -> str:
    """Return the welcome's message text, with the `hello` emoji slot in front."""
    return emoji.with_emoji(emoji.HELLO, texts.welcome)


async def handle_start(message: Message, texts: Texts) -> None:
    """Reply to `/start` with the welcome and its language button.

    Args:
        message: The `/start` message.
        texts: The user's catalog, injected by ``AccessMiddleware``.
    """
    await message.answer(welcome_text(texts), reply_markup=welcome_keyboard(texts))


def build_router() -> Router:
    """Create the `/start` router.

    A router can be attached to only one dispatcher, so it is built per call rather than
    kept at module level; that lets tests build a fresh dispatcher each time.
    """
    router = Router(name="start")
    router.message.register(handle_start, CommandStart())
    return router
