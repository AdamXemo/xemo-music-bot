from datetime import UTC, datetime
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    InaccessibleMessage,
    InlineKeyboardMarkup,
    Message,
    Update,
    User,
)
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from xemo_music_bot.bot import emoji
from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.bot.keyboards.language import PickerOrigin, PickLanguageCallback
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
    # No language picked yet, as for a user who just joined.
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


async def stored_language(connection: AsyncConnection) -> tuple[str, bool]:
    """Return the member's stored language and whether it was picked."""
    query = select(DbUser.language, DbUser.language_chosen).where(DbUser.tg_id == MEMBER_ID)
    row = (await connection.execute(query)).one()
    return row.language, row.language_chosen


async def mark_language_picked(connection: AsyncConnection) -> None:
    await connection.execute(
        update(DbUser).where(DbUser.tg_id == MEMBER_ID).values(language_chosen=True)
    )


def assert_picker(markup: object, origin: PickerOrigin) -> None:
    assert isinstance(markup, InlineKeyboardMarkup)
    [row] = markup.inline_keyboard
    # Flag, space, name: the labels as the spec spells them.
    assert [button.text for button in row] == ["🇬🇧 English", "🇺🇦 Українська", "🇷🇺 Русский"]
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
    # The edit drops the picker's buttons.
    assert edit.reply_markup is None
    return edit


@pytest.mark.parametrize("text", ["/start", "/start some-code"])
async def test_start_before_a_pick_sends_picker_as_new_message(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher, text: str
) -> None:
    await dispatcher.feed_update(bot, make_command(text))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.text == UK.language_prompt
    assert_picker(request.reply_markup, PickerOrigin.FIRST_RUN)


async def test_language_command_sends_picker_as_new_message(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_command("/language"))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.text == UK.language_prompt
    assert_picker(request.reply_markup, PickerOrigin.COMMAND)


# Picking the current language ("uk") is handled exactly like a change, and a first-run
# picker tapped after a pick (a stale one, or a second `/start`) works like the first time.
@pytest.mark.parametrize(
    ("language", "texts", "picked_before"),
    [
        pytest.param("ru", RU, False, id="change"),
        pytest.param("uk", UK, False, id="current-language"),
        pytest.param("en", EN, True, id="stale-picker-after-a-pick"),
    ],
)
async def test_first_run_pick_saves_and_edits_picker_into_welcome_in_that_language(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
    language: Language,
    texts: Texts,
    picked_before: bool,
) -> None:
    if picked_before:
        await mark_language_picked(connection)

    await dispatcher.feed_update(bot, make_tap(pick(language, PickerOrigin.FIRST_RUN)))

    assert await stored_language(connection) == (language, True)
    assert answered_edit(sent_requests).text == texts.welcome


async def test_first_run_pick_keeps_hello_emoji_in_new_language(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(emoji, "HELLO", emoji.CustomEmoji(emoji_id="1", alt="\N{WAVING HAND SIGN}"))

    await dispatcher.feed_update(bot, make_tap(pick("ru", PickerOrigin.FIRST_RUN)))

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
        await dispatcher.feed_update(bot, make_tap(pick("ru", PickerOrigin.FIRST_RUN)))

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

    assert await stored_language(connection) == (language, True)
    assert answered_edit(sent_requests).text == texts.language_set


async def test_pick_from_command_makes_the_next_start_send_the_welcome(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    await dispatcher.feed_update(bot, make_tap(pick("ru", PickerOrigin.COMMAND)))
    sent_requests.clear()

    await dispatcher.feed_update(bot, make_command("/start"))

    [request] = sent_requests
    assert isinstance(request, SendMessage)
    assert request.text == RU.welcome
    assert request.reply_markup is None


@pytest.mark.parametrize(
    "data",
    [
        pytest.param("language:de:first_run", id="unsupported-language"),
        pytest.param("language:ru:welcome", id="unknown-origin"),
        pytest.param("language:ru", id="missing-part"),
        # The welcome's "Language" button, removed before release.
        pytest.param("language_picker", id="old-welcome-button"),
    ],
)
async def test_unrecognised_button_is_answered_and_keyboard_removed(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
    data: str,
) -> None:
    await dispatcher.feed_update(bot, make_tap(data))

    answer, edit = sent_requests
    assert isinstance(answer, AnswerCallbackQuery)
    assert answer.text is None
    assert isinstance(edit, EditMessageReplyMarkup)
    assert (edit.chat_id, edit.message_id, edit.reply_markup) == (MEMBER_ID, MESSAGE_ID, None)
    assert await stored_language(connection) == ("uk", False)


async def test_pick_on_deleted_message_saves_and_answers_without_edit(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
) -> None:
    tap = make_tap(pick("ru", PickerOrigin.FIRST_RUN), accessible=False)

    await dispatcher.feed_update(bot, tap)

    assert await stored_language(connection) == ("ru", True)
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

    await dispatcher.feed_update(bot, make_tap(pick("uk", PickerOrigin.FIRST_RUN)))

    answered_edit(sent_requests)


async def test_other_edit_errors_propagate_and_roll_back_the_pick(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fail_edits(bot, sent_requests, monkeypatch, "Bad Request: message to edit not found")

    with pytest.raises(TelegramBadRequest, match="message to edit not found"):
        await dispatcher.feed_update(bot, make_tap(pick("ru", PickerOrigin.FIRST_RUN)))

    assert await stored_language(connection) == ("uk", False)
