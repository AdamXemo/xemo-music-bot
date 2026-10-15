from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import Chat, Message, Update, User
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from xemo_music_bot.bot import emoji
from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.bot.locales.ru import RU
from xemo_music_bot.core.services.search import SearchService
from xemo_music_bot.db.models import User as DbUser

CHAT_ID = 42


@pytest.fixture
async def dispatcher(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    search_service: SearchService,
) -> Dispatcher:
    # A member who has picked "ru" while Telegram says "uk". The first-run picker that
    # `/start` sends before a pick is covered in test_language.py.
    await session.execute(
        insert(DbUser).values(tg_id=CHAT_ID, role="user", language="ru", language_chosen=True)
    )
    return build_dispatcher(session_factory, frozenset(), search_service)


def make_update(text: str) -> Update:
    user = User(id=CHAT_ID, is_bot=False, first_name="Friend", language_code="uk")
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=CHAT_ID, type="private"),
        from_user=user,
        text=text,
    )
    return Update(update_id=1, message=message)


async def test_start_after_a_pick_sends_welcome_without_keyboard(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_update("/start"))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.chat_id == CHAT_ID
    # The stored language, not Telegram's; an empty emoji slot renders nothing.
    assert request.text == RU.welcome
    assert request.reply_markup is None


async def test_start_shows_hello_emoji_once_the_slot_is_set(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(emoji, "HELLO", emoji.CustomEmoji(emoji_id="1", alt="\N{WAVING HAND SIGN}"))

    await dispatcher.feed_update(bot, make_update("/start"))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.text == f'<tg-emoji emoji-id="1">\N{WAVING HAND SIGN}</tg-emoji> {RU.welcome}'


async def test_other_text_is_not_answered_by_start(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_update("hello"))

    assert sent_requests == []
