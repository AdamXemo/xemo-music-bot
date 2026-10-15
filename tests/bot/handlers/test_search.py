import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    SendChatAction,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    Message,
    MessageAutoDeleteTimerChanged,
    MessageEntity,
    Update,
    User,
    Voice,
)
from redis.asyncio import Redis
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from xemo_music_bot.bot import emoji
from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.bot.keyboards.results import TrackCallback
from xemo_music_bot.bot.labels import result_label
from xemo_music_bot.bot.locales.ru import RU
from xemo_music_bot.core.models import Track
from xemo_music_bot.core.services.search import SearchService
from xemo_music_bot.db.models import User as DbUser
from xemo_music_bot.db.repositories.search_sessions import SearchSessionsRepository
from xemo_music_bot.providers.base import ProviderError

MEMBER_ID = 2
OTHER_ID = 3
MESSAGE_ID = 7


def make_tracks(count: int) -> list[Track]:
    return [
        Track("soundcloud", str(n), f"Song {n}", "Artist", 200 + n, None, f"https://sc/{n}")
        for n in range(count)
    ]


class FakeProvider:
    """Returns canned tracks, or fails, and records the queries it got."""

    def __init__(self) -> None:
        self.tracks = make_tracks(12)
        self.error: Exception | None = None
        self.queries: list[str] = []

    async def search(self, query: str, limit: int) -> list[Track]:
        self.queries.append(query)
        # Yield once, as a real provider does, so the typing action can start.
        await asyncio.sleep(0)
        if self.error is not None:
            raise self.error
        return self.tracks[:limit]


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


# Overrides the conftest fixture: handlers here really search and keep sessions in Redis.
@pytest.fixture
def search_service(provider: FakeProvider, redis: Redis) -> SearchService:
    return SearchService(provider, SearchSessionsRepository(redis))


@pytest.fixture
async def dispatcher(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    search_service: SearchService,
) -> Dispatcher:
    # Stored "ru" while Telegram says "uk", so a reply shows which one it used.
    await session.execute(
        insert(DbUser).values(tg_id=MEMBER_ID, role="user", language="ru", language_chosen=True)
    )
    return build_dispatcher(session_factory, frozenset(), search_service)


def make_user() -> User:
    return User(id=MEMBER_ID, is_bot=False, first_name="Friend", language_code="uk")


def make_message(**content: Any) -> Update:
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=MEMBER_ID, type="private"),
        from_user=make_user(),
        **content,
    )
    return Update(update_id=1, message=message)


def make_tap(data: str) -> Update:
    message = Message(
        message_id=MESSAGE_ID,
        date=datetime.now(UTC),
        chat=Chat(id=MEMBER_ID, type="private"),
        text="old",
    )
    callback = CallbackQuery(
        id="tap", from_user=make_user(), chat_instance="1", message=message, data=data
    )
    return Update(update_id=1, callback_query=callback)


def only_reply(requests: list[TelegramMethod[Any]]) -> SendMessage:
    """Return the one message sent, ignoring chat actions."""
    [reply] = [request for request in requests if isinstance(request, SendMessage)]
    return reply


def keyboard_of(reply: SendMessage | EditMessageText) -> InlineKeyboardMarkup:
    assert isinstance(reply.reply_markup, InlineKeyboardMarkup)
    return reply.reply_markup


async def search(
    dispatcher: Dispatcher, bot: Bot, requests: list[TelegramMethod[Any]]
) -> InlineKeyboardMarkup:
    """Send a search and return the keyboard of the results message."""
    await dispatcher.feed_update(bot, make_message(text="daft punk"))
    return keyboard_of(only_reply(requests))


async def test_text_search_sends_results_message_with_a_button_per_track(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
) -> None:
    await dispatcher.feed_update(bot, make_message(text="  daft punk "))

    typing = [r for r in sent_requests if isinstance(r, SendChatAction)]
    assert typing
    assert {(r.chat_id, r.action) for r in typing} == {(MEMBER_ID, "typing")}
    assert provider.queries == ["daft punk"]
    reply = only_reply(sent_requests)
    assert reply.chat_id == MEMBER_ID
    assert reply.text == "<b>daft punk</b>"
    rows = keyboard_of(reply).inline_keyboard
    tracks = provider.tracks[:5]
    assert [[button.text for button in row] for row in rows[:5]] == [
        [result_label(track)] for track in tracks
    ]
    session_id = TrackCallback.unpack(rows[0][0].callback_data or "").session_id
    assert [row[0].callback_data for row in rows[:5]] == [
        f"track:{session_id}:{index}" for index in range(5)
    ]
    # Telegram rejects callback data over 64 bytes.
    assert all(len((row[0].callback_data or "").encode()) <= 64 for row in rows[:5])
    assert all(row[0].icon_custom_emoji_id is None for row in rows[:5])


async def test_pager_row_has_a_disabled_back_on_the_first_page(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    keyboard = await search(dispatcher, bot, sent_requests)

    back, counter, forward = keyboard.inline_keyboard[5]
    assert (back.text, counter.text, forward.text) == (RU.pager_back, "1 / 2", RU.pager_next)
    # A disabled button is a button with no action at all.
    assert back.disabled is not None
    assert back.callback_data is None
    assert counter.disabled is not None
    assert counter.callback_data is None
    assert forward.disabled is None
    assert forward.callback_data is not None
    assert forward.callback_data.startswith("page:")
    assert forward.callback_data.endswith(":1")


async def test_single_page_has_no_pager_row(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
) -> None:
    provider.tracks = make_tracks(3)

    keyboard = await search(dispatcher, bot, sent_requests)

    assert len(keyboard.inline_keyboard) == 3


async def test_track_buttons_get_the_track_icon_once_the_slot_is_set(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(emoji, "TRACK", emoji.CustomEmoji(emoji_id="99", alt="\N{MUSICAL NOTE}"))

    keyboard = await search(dispatcher, bot, sent_requests)

    assert [row[0].icon_custom_emoji_id for row in keyboard.inline_keyboard[:5]] == ["99"] * 5


async def test_results_header_escapes_the_query(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_message(text="<b>AC&DC"))

    reply = only_reply(sent_requests)
    assert reply.text == "<b>&lt;b&gt;AC&amp;DC</b>"


async def test_next_edits_the_same_message_to_the_last_page(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    keyboard = await search(dispatcher, bot, sent_requests)
    sent_requests.clear()

    await dispatcher.feed_update(bot, make_tap(keyboard.inline_keyboard[5][2].callback_data or ""))

    answer, edit = sent_requests
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text is None
    assert isinstance(edit, EditMessageText)
    assert (edit.chat_id, edit.message_id) == (MEMBER_ID, MESSAGE_ID)
    assert edit.text == "<b>daft punk</b>"
    rows = keyboard_of(edit).inline_keyboard
    assert [row[0].text for row in rows[:5]] == [
        result_label(track) for track in make_tracks(10)[5:]
    ]
    back, counter, forward = rows[5]
    assert (back.text, counter.text, forward.text) == (RU.pager_back, "2 / 2", RU.pager_next)
    assert back.callback_data is not None
    assert back.callback_data.endswith(":0")
    # The row keeps its three buttons; the arrow at the end is disabled, not removed.
    assert forward.disabled is not None
    assert forward.callback_data is None


@pytest.mark.parametrize("prefix", ["page", "track"])
async def test_tap_on_expired_results_shows_a_toast_and_removes_the_buttons(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher, prefix: str
) -> None:
    await dispatcher.feed_update(bot, make_tap(f"{prefix}:gone:1"))

    answer, edit = sent_requests
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text == RU.results_expired
    assert isinstance(edit, EditMessageReplyMarkup)
    assert (edit.chat_id, edit.message_id) == (MEMBER_ID, MESSAGE_ID)
    assert edit.reply_markup is None


async def test_tap_on_another_users_results_is_treated_as_expired(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    search_service: SearchService,
) -> None:
    page = await search_service.search(OTHER_ID, "private query")
    assert page is not None

    await dispatcher.feed_update(bot, make_tap(f"page:{page.session_id}:1"))

    answer, edit = sent_requests
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text == RU.results_expired
    assert isinstance(edit, EditMessageReplyMarkup)


async def test_track_tap_is_answered_silently_until_delivery_exists(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    keyboard = await search(dispatcher, bot, sent_requests)
    sent_requests.clear()

    await dispatcher.feed_update(bot, make_tap(keyboard.inline_keyboard[0][0].callback_data or ""))

    [answer] = sent_requests
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text is None


async def test_search_with_no_matches_replies_with_the_escaped_query(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
) -> None:
    provider.tracks = []

    await dispatcher.feed_update(bot, make_message(text="a<b"))

    reply = only_reply(sent_requests)
    assert reply.text == RU.no_results.format(query="a&lt;b")
    assert reply.reply_markup is None


async def test_provider_failure_replies_search_failed(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
) -> None:
    provider.error = ProviderError("boom")

    await dispatcher.feed_update(bot, make_message(text="daft punk"))

    reply = only_reply(sent_requests)
    assert reply.text == RU.search_failed
    assert reply.reply_markup is None


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param({"text": "x" * 101}, RU.query_too_long, id="too-long"),
        pytest.param(
            {
                "text": "see https://example.com",
                "entities": [MessageEntity(type="url", offset=4, length=19)],
            },
            RU.link_not_supported,
            id="url-entity",
        ),
        pytest.param(
            {
                "text": "this song",
                "entities": [
                    MessageEntity(type="text_link", offset=5, length=4, url="https://e.com")
                ],
            },
            RU.link_not_supported,
            id="hidden-link",
        ),
        pytest.param({"text": "https://example.com/a"}, RU.link_not_supported, id="url-text-only"),
        pytest.param(
            {"voice": Voice(file_id="f", file_unique_id="u", duration=1)}, RU.not_text, id="voice"
        ),
        pytest.param(
            {"text": "/nope daft punk"}, RU.unknown_command, id="unknown-command-with-args"
        ),
    ],
)
async def test_messages_that_are_not_searches_get_a_hint_and_no_search(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
    content: dict[str, Any],
    expected: str,
) -> None:
    await dispatcher.feed_update(bot, make_message(**content))

    reply = only_reply(sent_requests)
    assert reply.text == expected
    assert reply.reply_markup is None
    assert provider.queries == []


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(
            {
                "message_auto_delete_timer_changed": MessageAutoDeleteTimerChanged(
                    message_auto_delete_time=5
                )
            },
            id="auto-delete-timer",
        ),
        pytest.param(
            {
                "pinned_message": Message(
                    message_id=1, date=datetime.now(UTC), chat=Chat(id=1, type="private")
                )
            },
            id="pin",
        ),
    ],
)
async def test_service_messages_are_not_answered(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
    content: dict[str, Any],
) -> None:
    await dispatcher.feed_update(bot, make_message(**content))

    assert sent_requests == []
    assert provider.queries == []


async def test_query_of_exactly_100_characters_is_searched(
    bot: Bot, dispatcher: Dispatcher, provider: FakeProvider
) -> None:
    await dispatcher.feed_update(bot, make_message(text="x" * 100))

    assert provider.queries == ["x" * 100]


async def test_whitespace_only_text_is_ignored(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_message(text="\N{NO-BREAK SPACE} "))

    assert sent_requests == []
