"""`/start`: greet the user in their language."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from xemo_music_bot.bot.locales import Texts


async def handle_start(message: Message, texts: Texts) -> None:
    """Reply to `/start` with a short greeting.

    Args:
        message: The `/start` message.
        texts: The user's catalog, injected by ``AccessMiddleware``.
    """
    await message.answer(texts.greeting)


def build_router() -> Router:
    """Create the `/start` router.

    A router can be attached to only one dispatcher, so it is built per call rather than
    kept at module level; that lets tests build a fresh dispatcher each time.
    """
    router = Router(name="start")
    router.message.register(handle_start, CommandStart())
    return router
