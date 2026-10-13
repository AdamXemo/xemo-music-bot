from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import Chat, InlineKeyboardMarkup, Message, Update, User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from xemo_music_bot.bot import emoji
from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.bot.keyboards.language import OpenPickerCallback
from xemo_music_bot.bot.locales.en import EN
from xemo_music_bot.bot.locales.uk import UK

CHAT_ID = 42


@pytest.fixture
def dispatcher(session_factory: async_sessionmaker[AsyncSession]) -> Dispatcher:
    # The sender is a config admin, so every update passes the access check. These tests
    # cover a row created with Telegram's language; the stored-language case is in
    # tests/bot/middlewares/test_access.py.
    return build_dispatcher(session_factory, admin_ids=frozenset({CHAT_ID}))


def make_update(text: str, language_code: str | None) -> Update:
    user = User(id=CHAT_ID, is_bot=False, first_name="Friend", language_code=language_code)
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=CHAT_ID, type="private"),
        from_user=user,
        text=text,
    )
    return Update(update_id=1, message=message)


async def test_start_sends_welcome_with_language_button_in_user_language(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_update("/start", "uk"))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.chat_id == CHAT_ID
    assert request.text == UK.welcome
    assert isinstance(request.reply_markup, InlineKeyboardMarkup)
    [[button]] = request.reply_markup.inline_keyboard
    assert button.text == UK.language_button
    assert button.callback_data == OpenPickerCallback().pack()
    # Empty emoji slots render nothing.
    assert button.icon_custom_emoji_id is None


async def test_start_falls_back_to_english_for_unsupported_language(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_update("/start", "de"))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.text == EN.welcome


async def test_start_shows_emoji_slots_once_they_are_set(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(emoji, "HELLO", emoji.CustomEmoji(emoji_id="1", alt="\N{WAVING HAND SIGN}"))
    monkeypatch.setattr(
        emoji, "LANGUAGE", emoji.CustomEmoji(emoji_id="2", alt="\N{GLOBE WITH MERIDIANS}")
    )

    await dispatcher.feed_update(bot, make_update("/start", "en"))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.text == f'<tg-emoji emoji-id="1">\N{WAVING HAND SIGN}</tg-emoji> {EN.welcome}'
    assert isinstance(request.reply_markup, InlineKeyboardMarkup)
    [[button]] = request.reply_markup.inline_keyboard
    assert button.icon_custom_emoji_id == "2"


async def test_other_text_is_not_answered_by_start(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_update("hello", "en"))

    assert sent_requests == []
