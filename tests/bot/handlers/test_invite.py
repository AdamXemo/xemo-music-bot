import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import GetMe, SendMessage, SetMyCommands, TelegramMethod
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
    Update,
    User,
)
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from xemo_music_bot.bot.commands import build_commands
from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.bot.handlers.start import welcome_text
from xemo_music_bot.bot.invite_notice import friend_text
from xemo_music_bot.bot.locales import Texts
from xemo_music_bot.bot.locales.en import EN
from xemo_music_bot.bot.locales.ru import RU
from xemo_music_bot.bot.locales.uk import UK
from xemo_music_bot.core.services.delivery import DeliveryService
from xemo_music_bot.core.services.search import SearchService
from xemo_music_bot.db.models import Invite
from xemo_music_bot.db.models import User as DbUser

ADMIN_ID = 1
MEMBER_ID = 2
BLOCKED_ID = 3
STRANGER_ID = 4
CODE = "Kx7pQ2mZ"
BOT_USERNAME = "xemo_music_bot"


@pytest.fixture
async def seeded(session: AsyncSession) -> None:
    # Stored languages differ from the Telegram language each test sends ("en" unless
    # it says otherwise), so a reply shows which one it used.
    await session.execute(
        insert(DbUser),
        [
            {"tg_id": ADMIN_ID, "role": "user", "language": "ru", "language_chosen": True},
            {"tg_id": MEMBER_ID, "role": "user", "language": "uk", "language_chosen": True},
            {"tg_id": BLOCKED_ID, "role": "blocked", "language": "ru", "language_chosen": True},
        ],
    )


@pytest.fixture
def dispatcher(
    seeded: None,
    session_factory: async_sessionmaker[AsyncSession],
    search_service: SearchService,
    delivery_service: DeliveryService,
) -> Dispatcher:
    return build_dispatcher(
        session_factory, frozenset({ADMIN_ID}), search_service, delivery_service
    )


@pytest.fixture(autouse=True)
def telegram(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Answer getMe like Telegram; every other call is only recorded."""

    async def make_request(_bot: Bot, method: TelegramMethod[Any], **_kwargs: Any) -> Any:
        sent_requests.append(method)
        if isinstance(method, GetMe):
            return User(id=99, is_bot=True, first_name="Xemo", username=BOT_USERNAME)
        return None

    monkeypatch.setattr(bot.session, "make_request", make_request)


async def add_invite(session: AsyncSession, state: str = "working") -> None:
    """Store ``CODE``, created by the admin: working, used or expired."""
    values: dict[str, Any] = {
        "code": CODE,
        "created_by": ADMIN_ID,
        "expires_at": func.now() + timedelta(days=7),
    }
    if state == "used":
        values |= {"used_at": func.now(), "used_by": MEMBER_ID}
    elif state == "expired":
        values |= {
            "created_at": func.now() - timedelta(days=8),
            "expires_at": func.now() - timedelta(days=1),
        }
    await session.execute(insert(Invite).values(values))


def make_update(text: str, sender: User) -> Update:
    message = Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=sender.id, type="private"),
        from_user=sender,
        text=text,
    )
    return Update(update_id=1, message=message)


def person(
    tg_id: int,
    language_code: str = "en",
    first_name: str = "Friend",
    last_name: str | None = None,
    username: str | None = None,
) -> User:
    return User(
        id=tg_id,
        is_bot=False,
        language_code=language_code,
        first_name=first_name,
        last_name=last_name,
        username=username,
    )


def messages(requests: list[TelegramMethod[Any]]) -> list[SendMessage]:
    return [request for request in requests if isinstance(request, SendMessage)]


async def code_used_by(connection: AsyncConnection) -> int | None:
    return await connection.scalar(select(Invite.used_by).where(Invite.code == CODE))


async def test_admin_invite_replies_with_one_line_and_copy_and_share_buttons(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
) -> None:
    # Text after the command is ignored.
    await dispatcher.feed_update(bot, make_update("/invite for Anna", person(ADMIN_ID)))

    code = await connection.scalar(select(Invite.code).where(Invite.created_by == ADMIN_ID))
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    [reply] = messages(sent_requests)
    assert reply.chat_id == ADMIN_ID
    # The admin's stored language; the link is only on the buttons.
    assert reply.text == RU.invite_created == "<b>Одноразовое приглашение готово</b>"
    assert reply.link_preview_options == LinkPreviewOptions(is_disabled=True)
    assert isinstance(reply.reply_markup, InlineKeyboardMarkup)
    [[copy, share]] = reply.reply_markup.inline_keyboard
    assert (copy.text, share.text, copy.style, share.style) == (
        RU.invite_copy,
        RU.invite_share,
        None,
        None,
    )
    assert copy.copy_text is not None
    assert copy.copy_text.text == link
    assert share.url is not None
    shared = urlsplit(share.url)
    assert f"{shared.scheme}://{shared.netloc}{shared.path}" == "https://t.me/share/url"
    assert "+" not in shared.query
    assert parse_qs(shared.query) == {"url": [link], "text": [RU.invite_share_text]}


async def test_each_invite_gets_a_new_code_and_get_me_runs_once(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
) -> None:
    await dispatcher.feed_update(bot, make_update("/invite", person(ADMIN_ID)))
    await dispatcher.feed_update(bot, make_update("/invite", person(ADMIN_ID)))

    codes = (await connection.scalars(select(Invite.code))).all()
    assert len(set(codes)) == 2
    assert [type(request) for request in sent_requests].count(GetMe) == 1


async def test_member_invite_gets_unknown_command_and_creates_nothing(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    connection: AsyncConnection,
) -> None:
    await dispatcher.feed_update(bot, make_update("/invite", person(MEMBER_ID)))

    [reply] = messages(sent_requests)
    assert reply.text == UK.unknown_command
    assert await connection.scalar(select(func.count()).select_from(Invite)) == 0


async def test_stranger_with_a_working_code_joins_and_the_inviter_is_told(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    session: AsyncSession,
    connection: AsyncConnection,
) -> None:
    await add_invite(session)
    friend = person(STRANGER_ID, "uk", "Anna", "Kovalenko", "anna")

    await dispatcher.feed_update(bot, make_update(f"/start {CODE}", friend))

    notice, picker = messages(sent_requests)
    # The notice comes first, in the inviter's language.
    assert notice.chat_id == ADMIN_ID
    assert notice.text == RU.invite_joined.format(
        friend=RU.invite_friend.format(name="Anna Kovalenko", username="anna")
    )
    # Then the normal first-run `/start`, in the language detected from Telegram.
    assert (picker.chat_id, picker.text) == (STRANGER_ID, UK.language_prompt)
    row = (
        await connection.execute(
            select(DbUser.invited_by, DbUser.language).where(DbUser.tg_id == STRANGER_ID)
        )
    ).one()
    assert tuple(row) == (ADMIN_ID, "uk")
    assert await code_used_by(connection) == STRANGER_ID


async def test_undelivered_notice_is_logged_and_the_join_stands(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    session: AsyncSession,
    connection: AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await add_invite(session)

    async def make_request(_bot: Bot, method: TelegramMethod[Any], **_kwargs: Any) -> None:
        sent_requests.append(method)
        if isinstance(method, SendMessage) and method.chat_id == ADMIN_ID:
            raise TelegramForbiddenError(method, "Forbidden: bot was blocked by the user")

    monkeypatch.setattr(bot.session, "make_request", make_request)

    with caplog.at_level(logging.WARNING):
        await dispatcher.feed_update(bot, make_update(f"/start {CODE}", person(STRANGER_ID)))

    assert "bot was blocked by the user" in caplog.text
    assert messages(sent_requests)[-1].text == EN.language_prompt
    assert await code_used_by(connection) == STRANGER_ID


async def test_join_is_committed_before_the_inviter_is_told(
    bot: Bot, dispatcher: Dispatcher, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await add_invite(session)
    events: list[str] = []
    original_commit = AsyncSession.commit

    async def commit(self: AsyncSession) -> None:
        events.append("commit")
        await original_commit(self)

    async def make_request(_bot: Bot, method: TelegramMethod[Any], **_kwargs: Any) -> Any:
        if isinstance(method, SendMessage) and method.chat_id == ADMIN_ID:
            events.append("notice")
        if isinstance(method, GetMe):
            return User(id=99, is_bot=True, first_name="Xemo", username=BOT_USERNAME)
        return None

    monkeypatch.setattr(AsyncSession, "commit", commit)
    monkeypatch.setattr(bot.session, "make_request", make_request)

    await dispatcher.feed_update(bot, make_update(f"/start {CODE}", person(STRANGER_ID)))

    assert events[:2] == ["commit", "notice"]


async def test_join_stands_when_the_friends_start_reply_fails(
    bot: Bot,
    dispatcher: Dispatcher,
    session: AsyncSession,
    connection: AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await add_invite(session)

    async def make_request(_bot: Bot, method: TelegramMethod[Any], **_kwargs: Any) -> None:
        if isinstance(method, SendMessage) and method.chat_id == STRANGER_ID:
            raise TelegramForbiddenError(method, "Forbidden: bot was blocked by the user")

    monkeypatch.setattr(bot.session, "make_request", make_request)

    with pytest.raises(TelegramForbiddenError):
        await dispatcher.feed_update(bot, make_update(f"/start {CODE}", person(STRANGER_ID)))

    assert await code_used_by(connection) == STRANGER_ID


@pytest.mark.parametrize(
    ("text", "state", "language_code", "texts"),
    [
        pytest.param(f"/start {CODE}", "unknown", "en", EN, id="en:unknown"),
        pytest.param(f"/start {CODE}", "used", "en", EN, id="en:used"),
        pytest.param(f"/start {CODE}", "expired", "en", EN, id="en:expired"),
        pytest.param("/start some-code", "working", "en", EN, id="en:malformed"),
        pytest.param(
            f"/start@{BOT_USERNAME} {CODE}x", "working", "en", EN, id="en:malformed-with-bot-name"
        ),
        pytest.param(f"/start {CODE}", "unknown", "uk", UK, id="uk:unknown"),
        pytest.param(f"/start {CODE}", "unknown", "ru", RU, id="ru:unknown"),
    ],
)
async def test_stranger_with_a_code_that_does_not_work_gets_invite_invalid(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    session: AsyncSession,
    connection: AsyncConnection,
    text: str,
    state: str,
    language_code: str,
    texts: Texts,
) -> None:
    if state != "unknown":
        await add_invite(session, state)

    await dispatcher.feed_update(bot, make_update(text, person(STRANGER_ID, language_code)))

    [reply] = sent_requests
    assert isinstance(reply, SendMessage)
    assert (reply.chat_id, reply.text, reply.reply_markup) == (
        STRANGER_ID,
        texts.invite_invalid,
        None,
    )
    assert await connection.scalar(select(DbUser).where(DbUser.tg_id == STRANGER_ID)) is None


async def test_blocked_user_with_a_working_code_gets_private_bot_and_the_code_stays(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    session: AsyncSession,
    connection: AsyncConnection,
) -> None:
    await add_invite(session)

    await dispatcher.feed_update(bot, make_update(f"/start {CODE}", person(BLOCKED_ID)))

    [reply] = sent_requests
    assert isinstance(reply, SendMessage)
    assert reply.text == EN.private_bot
    assert await code_used_by(connection) is None


@pytest.mark.parametrize(("tg_id", "texts"), [(MEMBER_ID, UK), (ADMIN_ID, RU)])
async def test_member_or_admin_opening_an_invite_gets_the_normal_start(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    dispatcher: Dispatcher,
    session: AsyncSession,
    connection: AsyncConnection,
    tg_id: int,
    texts: Texts,
) -> None:
    await add_invite(session)

    await dispatcher.feed_update(bot, make_update(f"/start {CODE}", person(tg_id)))

    # Only the welcome: no notice to the admin, and the code is not used.
    [reply] = sent_requests
    assert isinstance(reply, SendMessage)
    assert (reply.chat_id, reply.text) == (tg_id, welcome_text(texts))
    assert await code_used_by(connection) is None


async def test_admin_keeps_invite_in_the_menu_after_a_language_pick(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], dispatcher: Dispatcher
) -> None:
    chat = Chat(id=ADMIN_ID, type="private")
    message = Message(message_id=7, date=datetime.now(UTC), chat=chat, text="old")
    callback = CallbackQuery(
        id="tap",
        from_user=person(ADMIN_ID),
        chat_instance="1",
        message=message,
        data="language:uk:command",
    )

    await dispatcher.feed_update(bot, Update(update_id=1, callback_query=callback))

    [menu] = [request for request in sent_requests if isinstance(request, SetMyCommands)]
    assert menu.commands == build_commands(UK, is_admin=True)


@pytest.mark.parametrize(
    ("first", "last", "username", "expected"),
    [
        pytest.param("Anna", None, None, "Anna", id="no-username"),
        pytest.param("Anna", None, "anna", "Anna (@anna)", id="username"),
        pytest.param(
            "<b>Tom", "& Jerry</b>", None, "&lt;b&gt;Tom &amp; Jerry&lt;/b&gt;", id="html-escaped"
        ),
        pytest.param("Anna\nMaria", None, None, "Anna Maria", id="newline-to-space"),
        pytest.param("A" * 40, None, None, "A" * 40, id="40-fits"),
        pytest.param("A" * 41, None, None, "A" * 39 + "…", id="cut-to-40"),
        # Cut first, then escape: the cut counts "<", not "&lt;".
        pytest.param("A" * 38 + "<b>", None, None, "A" * 38 + "&lt;…", id="cut-before-escape"),
        pytest.param(
            "\N{GRINNING FACE}" * 21,
            None,
            None,
            "\N{GRINNING FACE}" * 19 + "…",
            id="emoji-count-as-2-and-stay-whole",
        ),
    ],
)
def test_friend_name_in_the_notice(
    first: str, last: str | None, username: str | None, expected: str
) -> None:
    friend = person(STRANGER_ID, first_name=first, last_name=last, username=username)
    actual = friend_text(friend, EN)
    assert actual == expected, f"{first!r} {last!r}: expected {expected!r}, got {actual!r}"
