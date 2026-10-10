"""`/start`: greet the user in their Telegram language."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from xemo_music_bot.bot.locales import detect_language, get_texts


async def handle_start(message: Message) -> None:
    """Reply to `/start` with a short greeting."""
    language_code = message.from_user.language_code if message.from_user else None
    texts = get_texts(detect_language(language_code))
    await message.answer(texts.greeting)


def build_router() -> Router:
    """Create the `/start` router.

    A router can be attached to only one dispatcher, so it is built per call rather than
    kept at module level; that lets tests build a fresh dispatcher each time.
    """
    router = Router(name="start")
    router.message.register(handle_start, CommandStart())
    return router
