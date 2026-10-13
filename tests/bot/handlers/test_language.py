from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery, EditMessageText, SendMessage, TelegramMethod
from aiogram.types import (
    CallbackQuery,
    Chat,
    InaccessibleMessage,
    InlineKeyboardMarkup,
    Message,
    Update,
    User,
)
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from xemo_music_bot.bot import emoji
from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.bot.keyboards.language import (
    OpenPickerCallback,
    PickerOrigin,
    PickLanguageCallback,
)
from xemo_music_bot.bot.locales import Language, Texts
from xemo_music_bot.bot.locales.en import EN
from xemo_music_bot.bot.locales.ru import RU
from xemo_music_bot.bot.locales.uk import UK
from xemo_music_bot.core.services.language import LanguageService
from xemo_music_bot.db.models import User as DbUser

MEMBER_ID = 2
MESSAGE_ID = 7


@pytest.fixture
async def seeded(session: AsyncSession) -> None:
    # Stored "uk" while every update says Telegram "en", so a reply shows which one it used.
    await session.execute(insert(DbUser).values(tg_id=MEMBER_ID, role="user", language="uk"))


@pytest.fixture
def dispatcher(seeded: None, session_factory: async_sessionmaker[AsyncSession]) -> Dispatcher:
    return build_dispatcher(session_factory, admin_ids=frozenset())


def make_user() -> User:
    return User(id=MEMBER_ID, is_bot=False, first_name="Friend", language_code="en")


def make_command(text: str) -> Update:
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=MEMBER_ID, type="private"),
        from_user=make_user(),
        text=text,
    )
    return Update(update_id=1, message=message)


def make_tap(data: str, *, accessible: bool = True) -> Update:
    chat = Chat(id=MEMBER_ID, type="private")
    message = (
        Message(message_id=MESSAGE_ID, date=datetime.now(UTC), chat=chat, text="old")
        if accessible
        else InaccessibleMessage(chat=chat, message_id=MESSAGE_ID, date=0)
    )
    callback = CallbackQuery(
        id="tap", from_user=make_user(), chat_instance="1", message=message, data=data
    )
    return Update(update_id=1, callback_query=callback)


def pick(language: str, origin: PickerOrigin) -> str:
    # Spelled out to pin the format: buttons on old messages keep sending it.
    return f"language:{language}:{origin.value}"


async def stored_language(connection: AsyncConnection) -> str | None:
    return await connection.scalar(select(DbUser.language).where(DbUser.tg_id == MEMBER_ID))


def assert_picker(markup: object, origin: PickerOrigin) -> None:
    assert isinstance(markup, InlineKeyboardMarkup)
    [row] = markup.inline_keyboard
    assert [button.text for button in row] == [EN.language_name, UK.language_name, RU.language_name]
    # The stored language ("uk") is highlighted, not Telegram's ("en").
    assert [button.style for button in row] == [None, "primary", None]
    assert [button.callback_data for button in row] == [
        PickLanguageCallback(language=language, origin=origin).pack()
        for language in ("en", "uk", "ru")
    ]


def answered_edit(requests: list[TelegramMethod[Any]]) -> EditMessageText:
    """Check the tap was answered without text, then its message edited; return the edit."""
    answer, edit = requests
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text is None
    assert isinstance(edit, EditMessageText)
    assert (edit.chat_id, edit.message_id) == (MEMBER_ID, MESSAGE_ID)
    return edit


async def test_language_command_sends_picker_as_new_message(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_command("/language"))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.text == UK.language_prompt
    assert_picker(request.reply_markup, PickerOrigin.COMMAND)


async def test_language_button_edits_welcome_into_picker(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_tap(OpenPickerCallback().pack()))

    edit = answered_edit(sent_requests)
    assert edit.text == UK.language_prompt
    assert_picker(edit.reply_markup, PickerOrigin.WELCOME)


# Picking the current language ("uk") is handled exactly like a change.
@pytest.mark.parametrize(
    ("language", "texts"),
    [pytest.param("ru", RU, id="change"), pytest.param("uk", UK, id="current-language")],
)
async def test_pick_from_welcome_saves_and_edits_back_to_welcome_in_that_language(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
    language: Language,
    texts: Texts,
) -> None:
    await dispatcher.feed_update(bot, make_tap(pick(language, PickerOrigin.WELCOME)))

    assert await stored_language(connection) == language
    edit = answered_edit(sent_requests)
    assert edit.text == texts.welcome
    assert isinstance(edit.reply_markup, InlineKeyboardMarkup)
    [[button]] = edit.reply_markup.inline_keyboard
    assert button.text == texts.language_button


async def test_pick_from_welcome_keeps_hello_emoji_in_new_language(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(emoji, "HELLO", emoji.CustomEmoji(emoji_id="1", alt="\N{WAVING HAND SIGN}"))

    await dispatcher.feed_update(bot, make_tap(pick("ru", PickerOrigin.WELCOME)))

    edit = answered_edit(sent_requests)
    assert edit.text == f'<tg-emoji emoji-id="1">\N{WAVING HAND SIGN}</tg-emoji> {RU.welcome}'


async def test_pick_is_answered_even_if_the_save_fails(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(*_args: Any) -> None:
        raise LookupError

    monkeypatch.setattr(LanguageService, "set_language", fail)

    with pytest.raises(LookupError):
        await dispatcher.feed_update(bot, make_tap(pick("ru", PickerOrigin.WELCOME)))

    [answer] = sent_requests
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text is None


@pytest.mark.parametrize(
    ("language", "texts"),
    [pytest.param("en", EN, id="change"), pytest.param("uk", UK, id="current-language")],
)
async def test_pick_from_command_saves_and_confirms_in_that_language_without_keyboard(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
    language: Language,
    texts: Texts,
) -> None:
    await dispatcher.feed_update(bot, make_tap(pick(language, PickerOrigin.COMMAND)))

    assert await stored_language(connection) == language
    edit = answered_edit(sent_requests)
    assert edit.text == texts.language_set
    assert edit.reply_markup is None


@pytest.mark.parametrize(
    "data",
    [
        pytest.param("language:de:welcome", id="unsupported-language"),
        pytest.param("language:ru:elsewhere", id="unknown-origin"),
        pytest.param("language:ru", id="missing-part"),
    ],
)
async def test_forged_pick_is_ignored_and_saves_nothing(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
    data: str,
) -> None:
    await dispatcher.feed_update(bot, make_tap(data))

    assert sent_requests == []
    assert await stored_language(connection) == "uk"


async def test_pick_on_deleted_message_saves_and_answers_without_edit(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
) -> None:
    await dispatcher.feed_update(bot, make_tap(pick("ru", PickerOrigin.WELCOME), accessible=False))

    assert await stored_language(connection) == "ru"
    [answer] = sent_requests
    assert isinstance(answer, AnswerCallbackQuery)


def fail_edits(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    monkeypatch: pytest.MonkeyPatch,
    description: str,
) -> None:
    # aiogram passes `timeout` by keyword; the fake has no use for it.
    async def make_request(_bot: Bot, method: TelegramMethod[Any], **_kwargs: Any) -> None:
        sent_requests.append(method)
        if isinstance(method, EditMessageText):
            raise TelegramBadRequest(method, description)

    monkeypatch.setattr(bot.session, "make_request", make_request)


async def test_edit_that_changes_nothing_is_ignored_after_answering(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fail_edits(bot, sent_requests, monkeypatch, "Bad Request: message is not modified")

    await dispatcher.feed_update(bot, make_tap(OpenPickerCallback().pack()))

    answered_edit(sent_requests)


async def test_other_edit_errors_are_not_swallowed(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fail_edits(bot, sent_requests, monkeypatch, "Bad Request: message to edit not found")

    with pytest.raises(TelegramBadRequest, match="message to edit not found"):
        await dispatcher.feed_update(bot, make_tap(OpenPickerCallback().pack()))
