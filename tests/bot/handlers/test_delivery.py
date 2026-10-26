import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    SendAudio,
    SendChatAction,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import CallbackQuery, Chat, InlineKeyboardMarkup, Message, Update, User
from redis.asyncio import Redis
from rich.console import Console
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from xemo_music_bot import timing
from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.bot.keyboards.results import PageCallback, TrackCallback
from xemo_music_bot.bot.labels import result_label
from xemo_music_bot.bot.locales.ru import RU
from xemo_music_bot.core.models import DownloadedAudio, Track
from xemo_music_bot.core.services.delivery import DeliveryService
from xemo_music_bot.core.services.search import SearchService
from xemo_music_bot.db.models import User as DbUser
from xemo_music_bot.db.repositories.search_sessions import SearchSessionsRepository
from xemo_music_bot.providers.base import (
    PreviewOnlyError,
    ProviderError,
    TooLargeError,
)

MEMBER_ID = 2
MESSAGE_ID = 7
MAX_DURATION = 1000
TRACKS = [
    Track("soundcloud", str(n), f"Song {n}", "Artist", 200 + n, None, f"https://sc/{n}")
    for n in range(7)
]
# One song is over the limit; the others fit.
TRACKS[3] = Track("soundcloud", "3", "Song 3", "Artist", MAX_DURATION + 1, None, "https://sc/3")


class FakeProvider:
    """Searches canned tracks; a download yields real small files, or fails on entry."""

    def __init__(self, audio: DownloadedAudio) -> None:
        self.audio = audio
        self.tracks = TRACKS
        self.error: Exception | None = None
        self.downloaded: list[Track] = []

    async def search(self, query: str, limit: int) -> list[Track]:
        return self.tracks[:limit]

    @asynccontextmanager
    async def download(self, track: Track) -> AsyncIterator[DownloadedAudio]:
        self.downloaded.append(track)
        # A real download takes a while; the chat action needs a few loop turns to start.
        await asyncio.sleep(0.01)
        if self.error is not None:
            raise self.error
        yield self.audio


@pytest.fixture
def provider(tmp_path: Path) -> FakeProvider:
    audio = tmp_path / "track.mp3"
    cover = tmp_path / "cover.jpg"
    audio.write_bytes(b"mp3")
    cover.write_bytes(b"jpg")
    return FakeProvider(DownloadedAudio(path=audio, duration=181, size=3, thumbnail=cover))


@pytest.fixture
def search_service(provider: FakeProvider, redis: Redis) -> SearchService:
    return SearchService(provider, SearchSessionsRepository(redis))


@pytest.fixture
def delivery_service(provider: FakeProvider) -> DeliveryService:
    return DeliveryService(provider, MAX_DURATION)


@pytest.fixture
async def dispatcher(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    search_service: SearchService,
    delivery_service: DeliveryService,
) -> Dispatcher:
    # Stored "ru" while Telegram says "uk", so a reply shows which one it used.
    await session.execute(
        insert(DbUser).values(tg_id=MEMBER_ID, role="user", language="ru", language_chosen=True)
    )
    return build_dispatcher(session_factory, frozenset(), search_service, delivery_service)


@pytest.fixture
async def session_id(search_service: SearchService) -> str:
    page = await search_service.search(MEMBER_ID, "artist")
    assert page is not None
    return page.session_id


def make_tap(data: str) -> Update:
    message = Message(
        message_id=MESSAGE_ID,
        date=datetime.now(UTC),
        chat=Chat(id=MEMBER_ID, type="private"),
        text="old",
    )
    callback = CallbackQuery(
        id="tap",
        from_user=User(id=MEMBER_ID, is_bot=False, first_name="Friend", language_code="uk"),
        chat_instance="1",
        message=message,
        data=data,
    )
    return Update(update_id=1, callback_query=callback)


def tap_track(session_id: str, index: int) -> Update:
    return make_tap(TrackCallback(session_id=session_id, index=index).pack())


def without_chat_actions(requests: list[TelegramMethod[Any]]) -> list[TelegramMethod[Any]]:
    return [request for request in requests if not isinstance(request, SendChatAction)]


def buttons(request: TelegramMethod[Any]) -> list[Any]:
    assert isinstance(request, EditMessageReplyMarkup)
    assert isinstance(request.reply_markup, InlineKeyboardMarkup)
    return [row[0] for row in request.reply_markup.inline_keyboard[:5]]


def assert_shows_no_loading(request: TelegramMethod[Any]) -> None:
    assert [button.text for button in buttons(request)] == [
        result_label(track) for track in TRACKS[:5]
    ]


def fail_requests(
    monkeypatch: pytest.MonkeyPatch,
    api_session: BaseSession,
    method: type[TelegramMethod[Any]],
    error: Callable[[TelegramMethod[Any]], Exception],
) -> None:
    """Make Telegram reject every call of one method, as the real API would."""
    make_request = api_session.make_request

    async def failing(bot: Bot, call: TelegramMethod[Any], **kwargs: Any) -> Any:
        result = await make_request(bot, call, **kwargs)  # recorded like any other call
        if isinstance(call, method):
            raise error(call)
        return result

    monkeypatch.setattr(api_session, "make_request", failing)


async def test_tap_sends_the_audio_while_the_button_shows_loading_then_restores(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
    search_service: SearchService,
    session_id: str,
) -> None:
    await dispatcher.feed_update(bot, tap_track(session_id, 1))

    # No other messages: the audio has no caption and no buttons, and errors say nothing.
    answer, loading, audio, restored = without_chat_actions(sent_requests)
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text is None
    assert [button.text for button in buttons(loading)] == [
        result_label(TRACKS[0]),
        RU.track_loading,
        *[result_label(track) for track in TRACKS[2:5]],
    ]
    assert buttons(loading)[1].disabled is not None
    assert buttons(loading)[1].callback_data is None
    assert isinstance(audio, SendAudio)
    assert audio.chat_id == MEMBER_ID
    assert (audio.performer, audio.title, audio.duration) == ("Artist", "Song 1", 181)
    assert audio.caption is None
    assert audio.reply_markup is None
    assert getattr(audio.audio, "path", None) == provider.audio.path
    assert getattr(audio.thumbnail, "path", None) == provider.audio.thumbnail
    assert_shows_no_loading(restored)
    assert [r.action for r in sent_requests if isinstance(r, SendChatAction)] == ["upload_document"]
    page = await search_service.current_page(MEMBER_ID, session_id)
    assert page is not None
    assert page.loading == frozenset()


async def test_tap_logs_its_blocks_when_timings_are_on(
    bot: Bot, dispatcher: Dispatcher, session_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="xemo_music_bot.timing")
    timing.configure("blocks", Console(file=StringIO(), force_terminal=False))
    try:
        await dispatcher.feed_update(bot, tap_track(session_id, 1))
    finally:
        timing.configure("off")

    # The fake provider times nothing itself, so only the handler's blocks show.
    assert [m for m in caplog.messages if m.startswith("▶")] == [
        "▶ deliver Artist - Song 1",
        "▶ deliver Artist - Song 1: buttons",
        "▶ deliver Artist - Song 1: upload",
        "▶ deliver Artist - Song 1: buttons back",
    ]


async def test_tap_on_a_loading_track_shows_a_toast_and_downloads_nothing(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
    search_service: SearchService,
    session_id: str,
) -> None:
    await search_service.start_loading(MEMBER_ID, session_id, 1)

    await dispatcher.feed_update(bot, tap_track(session_id, 1))

    [answer] = sent_requests
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text == RU.already_loading
    assert provider.downloaded == []


async def test_tap_on_a_track_too_long_for_telegram_alerts_and_downloads_nothing(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
    search_service: SearchService,
    session_id: str,
) -> None:
    await dispatcher.feed_update(bot, tap_track(session_id, 3))

    [answer] = sent_requests
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.show_alert is True
    assert answer.text == RU.too_long.format(duration="16:41")
    assert provider.downloaded == []
    # The claim made to read the track is released, so the button works again.
    assert await search_service.start_loading(MEMBER_ID, session_id, 3) is not None


@pytest.mark.parametrize(
    ("error", "text"),
    [
        pytest.param(TooLargeError(), RU.too_large, id="too-large"),
        pytest.param(PreviewOnlyError(), RU.track_unavailable, id="go-plus-preview"),
        pytest.param(ProviderError("boom"), RU.download_failed, id="source-failure"),
    ],
)
async def test_failed_download_sends_a_message_and_restores_the_button(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
    search_service: SearchService,
    session_id: str,
    error: ProviderError,
    text: str,
) -> None:
    provider.error = error

    await dispatcher.feed_update(bot, tap_track(session_id, 1))

    _, _, message, restored = without_chat_actions(sent_requests)
    assert isinstance(message, SendMessage)
    assert message.chat_id == MEMBER_ID
    assert message.text == text.format(track="Artist - Song 1")
    assert_shows_no_loading(restored)
    page = await search_service.current_page(MEMBER_ID, session_id)
    assert page is not None
    assert page.loading == frozenset()


async def test_telegram_rejecting_the_upload_is_reported_as_a_failed_download(
    bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
    api_session: BaseSession,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    session_id: str,
) -> None:
    fail_requests(
        monkeypatch, api_session, SendAudio, lambda call: TelegramNetworkError(call, "timeout")
    )

    await dispatcher.feed_update(bot, tap_track(session_id, 1))

    _, _, _, message, restored = without_chat_actions(sent_requests)
    assert isinstance(message, SendMessage)
    assert message.text == RU.download_failed.format(track="Artist - Song 1")
    assert_shows_no_loading(restored)


async def test_deleting_the_results_message_mid_download_does_not_stop_the_audio(
    bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
    api_session: BaseSession,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    search_service: SearchService,
    session_id: str,
) -> None:
    fail_requests(
        monkeypatch,
        api_session,
        EditMessageReplyMarkup,
        lambda call: TelegramBadRequest(call, "Bad Request: message to edit not found"),
    )

    await dispatcher.feed_update(bot, tap_track(session_id, 1))

    assert any(isinstance(request, SendAudio) for request in sent_requests)
    assert not any(isinstance(request, SendMessage) for request in sent_requests)
    assert await search_service.start_loading(MEMBER_ID, session_id, 1) is not None


async def test_paging_while_a_track_loads_keeps_its_button_loading(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    search_service: SearchService,
    session_id: str,
) -> None:
    await search_service.start_loading(MEMBER_ID, session_id, 1)

    await dispatcher.feed_update(bot, make_tap(PageCallback(session_id=session_id, page=0).pack()))

    edit = sent_requests[-1]
    assert isinstance(edit, EditMessageText)
    assert isinstance(edit.reply_markup, InlineKeyboardMarkup)
    labels = [row[0].text for row in edit.reply_markup.inline_keyboard[:5]]
    assert labels == [
        result_label(TRACKS[0]),
        RU.track_loading,
        *[result_label(track) for track in TRACKS[2:5]],
    ]


async def test_failed_callback_answer_releases_the_claim(
    bot: Bot,
    monkeypatch: pytest.MonkeyPatch,
    api_session: BaseSession,
    dispatcher: Dispatcher,
    provider: FakeProvider,
    search_service: SearchService,
    session_id: str,
) -> None:
    fail_requests(
        monkeypatch,
        api_session,
        AnswerCallbackQuery,
        lambda call: TelegramBadRequest(call, "Bad Request: query is too old"),
    )

    with pytest.raises(TelegramBadRequest):
        await dispatcher.feed_update(bot, tap_track(session_id, 1))

    assert provider.downloaded == []
    assert await search_service.start_loading(MEMBER_ID, session_id, 1) is not None


async def test_unexpected_error_while_sending_still_releases_the_claim_and_restores_the_button(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
    search_service: SearchService,
    session_id: str,
) -> None:
    provider.error = OSError("disk full")

    with pytest.raises(OSError, match="disk full"):
        await dispatcher.feed_update(bot, tap_track(session_id, 1))

    assert_shows_no_loading(without_chat_actions(sent_requests)[-1])
    assert await search_service.start_loading(MEMBER_ID, session_id, 1) is not None


async def test_failure_message_escapes_the_track_name(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    provider: FakeProvider,
    search_service: SearchService,
) -> None:
    provider.tracks = [Track("soundcloud", "9", "A<b>&B", "", 200, None, "https://sc/9")]
    provider.error = ProviderError("boom")
    page = await search_service.search(MEMBER_ID, "escape")
    assert page is not None

    await dispatcher.feed_update(bot, tap_track(page.session_id, 0))

    [message] = [r for r in sent_requests if isinstance(r, SendMessage)]
    assert message.text == RU.download_failed.format(track="A&lt;b&gt;&amp;B")


def test_a_track_exactly_at_the_duration_limit_is_not_too_long(
    delivery_service: DeliveryService,
) -> None:
    at_limit = Track("soundcloud", "1", "t", "a", MAX_DURATION, None, "https://sc/1")
    over_limit = Track("soundcloud", "2", "t", "a", MAX_DURATION + 1, None, "https://sc/2")

    assert not delivery_service.is_too_long(at_limit)
    assert delivery_service.is_too_long(over_limit)
