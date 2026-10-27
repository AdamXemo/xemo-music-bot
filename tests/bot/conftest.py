from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager
from typing import Any, cast

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import TelegramMethod
from aiogram.methods.base import TelegramType
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from xemo_music_bot.core.models import DownloadedAudio, Track
from xemo_music_bot.core.services.delivery import DeliveryService
from xemo_music_bot.core.services.search import SearchService
from xemo_music_bot.db.repositories.search_sessions import SearchSessionsRepository
from xemo_music_bot.db.repositories.tracks import TracksRepository
from xemo_music_bot.db.session import create_session_factory


class RecordingSession(BaseSession):
    """Records Bot API calls instead of sending them to Telegram."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod[Any]] = []

    async def close(self) -> None:
        pass

    # The `timeout` parameters below mirror the abstract BaseSession signatures.
    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,  # noqa: ASYNC109 - fixed by BaseSession
    ) -> TelegramType:
        self.requests.append(method)
        # Handlers here ignore the API response, so a typed stub value is not needed.
        return cast("TelegramType", None)

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,  # noqa: ASYNC109 - fixed by BaseSession
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes]:
        yield b""


@pytest.fixture
def api_session() -> RecordingSession:
    return RecordingSession()


@pytest.fixture
def sent_requests(api_session: RecordingSession) -> list[TelegramMethod[Any]]:
    """Bot API calls the bot made, in order; a fixture so tests need not import conftest."""
    return api_session.requests


@pytest.fixture
def bot(api_session: RecordingSession) -> Bot:
    # A dummy token in the `<id>:<secret>` shape that Bot validates; it never reaches Telegram.
    return Bot(token="123456:TEST", session=api_session)  # noqa: S106


@pytest.fixture
def session_factory(connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    # Commits become savepoints on the test connection, so the test can see them and
    # the connection fixture still rolls everything back.
    return async_sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )


class NoProvider:
    """A provider for dispatcher tests that never search."""

    async def search(self, query: str, limit: int) -> list[Track]:
        raise AssertionError("These tests must not search")

    def download(self, track: Track) -> AbstractAsyncContextManager[DownloadedAudio]:
        raise AssertionError("These tests must not download")


@pytest.fixture
def search_service(unreachable_redis: Redis) -> SearchService:
    # Redis is unreachable on purpose: a handler that unexpectedly uses it fails loudly.
    return SearchService(NoProvider(), SearchSessionsRepository(unreachable_redis))


@pytest.fixture
def delivery_service(unreachable_engine: AsyncEngine) -> DeliveryService:
    # Unreachable like Redis above: a handler that unexpectedly reads the cache fails loudly.
    tracks = TracksRepository(create_session_factory(unreachable_engine))
    return DeliveryService(NoProvider(), tracks, max_duration=1000)
