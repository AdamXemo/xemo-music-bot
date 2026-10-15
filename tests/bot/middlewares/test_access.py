from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.methods import AnswerCallbackQuery, SendMessage, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, TelegramObject, Update, User
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.bot.locales import Texts
from xemo_music_bot.bot.locales.en import EN
from xemo_music_bot.bot.locales.ru import RU
from xemo_music_bot.bot.locales.uk import UK
from xemo_music_bot.bot.middlewares.access import AccessMiddleware
from xemo_music_bot.core.services.search import SearchService
from xemo_music_bot.db.models import User as DbUser
from xemo_music_bot.db.session import create_session_factory

ADMIN_ID = 1
MEMBER_ID = 2
BLOCKED_ID = 3
STRANGER_ID = 4
GROUP_ID = -100


@pytest.fixture
async def seeded(session: AsyncSession) -> None:
    await session.execute(
        # A multi-row VALUES takes its columns from the first row, so every row names
        # the same columns. The stored languages deliberately differ from the Telegram
        # languages the tests send, so a test shows which of the two a reply used.
        insert(DbUser).values(
            [
                {"tg_id": MEMBER_ID, "role": "user", "language": "uk"},
                {"tg_id": BLOCKED_ID, "role": "blocked", "language": "ru"},
            ]
        )
    )


@pytest.fixture
def dispatcher(
    seeded: None,
    session_factory: async_sessionmaker[AsyncSession],
    search_service: SearchService,
) -> Dispatcher:
    return build_dispatcher(session_factory, frozenset({ADMIN_ID}), search_service)


@pytest.fixture
def offline_dispatcher(
    unreachable_engine: AsyncEngine, search_service: SearchService
) -> Dispatcher:
    # Any database query fails loudly, which proves an update was dropped without one.
    return build_dispatcher(
        create_session_factory(unreachable_engine), frozenset({ADMIN_ID}), search_service
    )


def make_update(
    text: str, user_id: int, *, chat_type: str = "private", language_code: str = "en"
) -> Update:
    user = User(id=user_id, is_bot=False, first_name="Friend", language_code=language_code)
    chat_id = user_id if chat_type == "private" else GROUP_ID
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=chat_id, type=chat_type),
        from_user=user,
        text=text,
    )
    return Update(update_id=1, message=message)


@pytest.mark.parametrize("text", ["/start", "/start some-code", "/start@xemo_bot"])
@pytest.mark.parametrize(("language_code", "expected"), [("en", EN), ("uk", UK), ("ru", RU)])
async def test_stranger_start_gets_private_bot_line(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    text: str,
    language_code: str,
    expected: Texts,
) -> None:
    await dispatcher.feed_update(bot, make_update(text, STRANGER_ID, language_code=language_code))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.chat_id == STRANGER_ID
    assert request.text == expected.private_bot
    assert request.reply_markup is None


@pytest.mark.parametrize(
    "text", ["hello", "/help", "/started", pytest.param(chr(160), id="whitespace-only")]
)
async def test_stranger_other_messages_are_ignored(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher, text: str
) -> None:
    await dispatcher.feed_update(bot, make_update(text, STRANGER_ID))

    assert sent_requests == []


async def test_blocked_user_start_gets_private_bot_line(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_update("/start", BLOCKED_ID))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.text == EN.private_bot


async def test_member_start_is_answered_in_the_stored_language(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_update("/start", MEMBER_ID, language_code="ru"))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    # The first-run picker, since the seeded rows have not picked a language yet.
    assert request.text == UK.language_prompt


async def test_config_admin_first_start_creates_row_and_reaches_the_handler(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
) -> None:
    await dispatcher.feed_update(bot, make_update("/start", ADMIN_ID))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.text == EN.language_prompt
    role = await connection.scalar(select(DbUser.role).where(DbUser.tg_id == ADMIN_ID))
    assert role == "user"


@pytest.mark.parametrize("user_id", [STRANGER_ID, ADMIN_ID])
@pytest.mark.parametrize("chat_type", ["group", "supergroup"])
async def test_group_messages_are_ignored_without_a_query(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    offline_dispatcher: Dispatcher,
    user_id: int,
    chat_type: str,
) -> None:
    await offline_dispatcher.feed_update(bot, make_update("/start", user_id, chat_type=chat_type))

    assert sent_requests == []


async def test_group_callback_is_answered_without_text_or_a_query(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], offline_dispatcher: Dispatcher
) -> None:
    sender = User(id=ADMIN_ID, is_bot=False, first_name="Friend")
    message = Message(
        message_id=1, date=datetime.now(UTC), chat=Chat(id=GROUP_ID, type="group"), text="old"
    )
    callback = CallbackQuery(
        id="1", from_user=sender, chat_instance="1", message=message, data="language_picker"
    )

    await offline_dispatcher.feed_update(bot, Update(update_id=1, callback_query=callback))

    [answer] = sent_requests
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text is None


async def test_update_without_sender_is_ignored_without_a_query(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], offline_dispatcher: Dispatcher
) -> None:
    await offline_dispatcher.feed_update(bot, Update(update_id=1))

    assert sent_requests == []


@pytest.mark.parametrize(
    ("user_id", "is_admin", "stored", "texts"),
    [
        # The member's stored 'uk' wins over Telegram's 'ru-RU'.
        pytest.param(MEMBER_ID, False, "uk", UK, id="member-stored-language"),
        # The admin has no row yet, so it is created with Telegram's language.
        pytest.param(ADMIN_ID, True, "ru", RU, id="admin-new-row-from-telegram"),
    ],
)
async def test_allowed_sender_reaches_handler_with_row_admin_flag_and_texts(
    seeded: None,
    session: AsyncSession,
    user_id: int,
    is_admin: bool,
    stored: str,
    texts: Texts,
) -> None:
    sender = User(id=user_id, is_bot=False, first_name="Friend", language_code="ru-RU")
    data: dict[str, Any] = {
        "session": session,
        "event_from_user": sender,
        "event_chat": Chat(id=user_id, type="private"),
    }

    async def handler(event: TelegramObject, data: dict[str, Any]) -> str:
        return "handled"

    middleware = AccessMiddleware(frozenset({ADMIN_ID}))
    result = await middleware(handler, Update(update_id=1), data)

    assert result == "handled"
    assert data["db_user"].tg_id == user_id
    assert data["is_admin"] is is_admin
    assert data["texts"] is texts
    language = await session.scalar(select(DbUser.language).where(DbUser.tg_id == user_id))
    assert language == stored


@pytest.mark.parametrize("kind", ["message", "edited_message", "callback_query"])
@pytest.mark.parametrize("user_id", [STRANGER_ID, BLOCKED_ID])
async def test_denied_sender_never_reaches_a_handler(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    seeded: None,
    session: AsyncSession,
    user_id: int,
    kind: str,
) -> None:
    sender = User(id=user_id, is_bot=False, first_name="Friend")
    chat = Chat(id=user_id, type="private")
    data: dict[str, Any] = {"session": session, "event_from_user": sender, "event_chat": chat}
    if kind == "message":
        message = Message(
            message_id=1, date=datetime.now(UTC), chat=chat, from_user=sender, text="hello"
        )
        update = Update(update_id=1, message=message)
    elif kind == "edited_message":
        # An edited `/start` is not a new command, so it gets no reply either.
        message = Message(
            message_id=1, date=datetime.now(UTC), chat=chat, from_user=sender, text="/start"
        )
        update = Update(update_id=1, edited_message=message)
    else:
        # A callback query without its message carries no chat.
        del data["event_chat"]
        # Bound by hand: only the dispatcher binds updates to a bot, and the deny path
        # answers the callback through it.
        callback = CallbackQuery(id="1", from_user=sender, chat_instance="1").as_(bot)
        update = Update(update_id=1, callback_query=callback)
    calls: list[TelegramObject] = []

    async def handler(event: TelegramObject, data: dict[str, Any]) -> None:
        calls.append(event)

    result = await AccessMiddleware(frozenset({ADMIN_ID}))(handler, update, data)

    assert result is None
    assert calls == []
    if kind == "callback_query":
        # Answered without text, so an old button stops spinning; nothing else is sent.
        [answer] = sent_requests
        assert isinstance(answer, AnswerCallbackQuery)
        assert answer.text is None
    else:
        assert sent_requests == []
