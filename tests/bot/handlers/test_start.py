from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.methods.base import TelegramType
from aiogram.types import Chat, Message, Update, User

from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.bot.locales.en import EN
from xemo_music_bot.bot.locales.uk import UK

CHAT_ID = 42


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
def session() -> RecordingSession:
    return RecordingSession()


@pytest.fixture
def bot(session: RecordingSession) -> Bot:
    # A dummy token in the `<id>:<secret>` shape that Bot validates; it never reaches Telegram.
    return Bot(token="123456:TEST", session=session)  # noqa: S106


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


async def test_start_replies_with_greeting_in_user_language(
    bot: Bot, session: RecordingSession
) -> None:
    await build_dispatcher().feed_update(bot, make_update("/start", "uk"))

    [request] = session.requests
    assert isinstance(request, SendMessage)
    assert request.chat_id == CHAT_ID
    assert request.text == UK.greeting


async def test_start_falls_back_to_english_for_unsupported_language(
    bot: Bot, session: RecordingSession
) -> None:
    await build_dispatcher().feed_update(bot, make_update("/start", "de"))

    [request] = session.requests
    assert isinstance(request, SendMessage)
    assert request.text == EN.greeting


async def test_other_text_is_not_answered_by_start(bot: Bot, session: RecordingSession) -> None:
    await build_dispatcher().feed_update(bot, make_update("hello", "en"))

    assert session.requests == []
