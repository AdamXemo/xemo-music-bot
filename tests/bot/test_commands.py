import logging
from functools import partial
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    SetMyCommands,
    SetMyDescription,
    SetMyShortDescription,
    TelegramMethod,
)
from aiogram.types import BotCommand, BotCommandScopeChat
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from xemo_music_bot.bot.commands import build_commands, publish_commands, set_user_commands
from xemo_music_bot.bot.locales import Language, Texts
from xemo_music_bot.bot.locales.en import EN
from xemo_music_bot.bot.locales.ru import RU
from xemo_music_bot.bot.locales.uk import UK
from xemo_music_bot.db.models import User

ADMIN_ID = 1
OTHER_ADMIN_ID = 3
LANGUAGES: list[tuple[str | None, Texts]] = [(None, EN), ("en", EN), ("uk", UK), ("ru", RU)]


def chat_menus(requests: list[TelegramMethod[Any]]) -> list[tuple[int, list[BotCommand]]]:
    """Return (chat ID, commands) of every chat-scope menu that was set."""
    return [
        (int(request.scope.chat_id), request.commands)
        for request in requests
        if isinstance(request, SetMyCommands) and isinstance(request.scope, BotCommandScopeChat)
    ]


def fail_chat_menus(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    # aiogram passes `timeout` by keyword; the fake has no use for it.
    async def make_request(_bot: Bot, method: TelegramMethod[Any], **_kwargs: Any) -> None:
        sent_requests.append(method)
        if isinstance(method, SetMyCommands) and isinstance(method.scope, BotCommandScopeChat):
            raise TelegramBadRequest(method, "Bad Request: chat not found")

    monkeypatch.setattr(bot.session, "make_request", make_request)


def test_menu_lists_only_commands_that_exist_in_the_texts_language() -> None:
    assert build_commands(UK) == [
        BotCommand(command="start", description="Запустити бота"),
        BotCommand(command="language", description="Змінити мову"),
    ]


def test_admin_menu_adds_invite() -> None:
    assert build_commands(UK, is_admin=True) == [
        *build_commands(UK),
        BotCommand(command="invite", description="Створити запрошення"),
    ]


async def test_startup_publishes_menu_and_descriptions_per_language_and_a_default(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await publish_commands(session_factory, frozenset(), bot)

    # The default (no language_code) entry is English, for clients in other languages.
    expected: list[TelegramMethod[Any]] = []
    for code, texts in LANGUAGES:
        expected += [
            SetMyCommands(commands=build_commands(texts), language_code=code),
            SetMyDescription(description=texts.bot_description, language_code=code),
            SetMyShortDescription(
                short_description=texts.bot_short_description, language_code=code
            ),
        ]
    assert sent_requests == expected


async def test_startup_hook_registered_with_partial_receives_the_bot(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Mirrors the registration in `__main__.main`; polling emits startup with `bot=`.
    dispatcher = Dispatcher()
    dispatcher.startup.register(partial(publish_commands, session_factory, frozenset()))

    await dispatcher.emit_startup(bot=bot)

    assert len(sent_requests) == 12


async def test_startup_sets_each_admins_chat_menu_in_their_stored_language(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    session_factory: async_sessionmaker[AsyncSession],
    session: AsyncSession,
) -> None:
    await session.execute(
        insert(User),
        [
            {"tg_id": ADMIN_ID, "role": "user", "language": "uk"},
            {"tg_id": OTHER_ADMIN_ID, "role": "user", "language": "ru"},
            # Not an admin: no chat menu from startup.
            {"tg_id": 9, "role": "user", "language": "ru"},
        ],
    )

    await publish_commands(session_factory, frozenset({ADMIN_ID, OTHER_ADMIN_ID}), bot)

    assert chat_menus(sent_requests) == [
        (ADMIN_ID, build_commands(UK, is_admin=True)),
        (OTHER_ADMIN_ID, build_commands(RU, is_admin=True)),
    ]


async def test_startup_skips_an_admin_without_a_row(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    session_factory: async_sessionmaker[AsyncSession],
    session: AsyncSession,
) -> None:
    await session.execute(insert(User).values(tg_id=ADMIN_ID, role="user", language="uk"))

    await publish_commands(session_factory, frozenset({ADMIN_ID, OTHER_ADMIN_ID}), bot)

    assert chat_menus(sent_requests) == [(ADMIN_ID, build_commands(UK, is_admin=True))]


async def test_startup_logs_a_telegram_error_and_still_sets_the_other_admins(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    session_factory: async_sessionmaker[AsyncSession],
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await session.execute(
        insert(User),
        [
            {"tg_id": ADMIN_ID, "role": "user", "language": "uk"},
            {"tg_id": OTHER_ADMIN_ID, "role": "user", "language": "ru"},
        ],
    )
    fail_chat_menus(bot, sent_requests, monkeypatch)

    with caplog.at_level(logging.WARNING):
        await publish_commands(session_factory, frozenset({ADMIN_ID, OTHER_ADMIN_ID}), bot)

    # Both were tried: one failure does not stop the next admin.
    assert [chat_id for chat_id, _ in chat_menus(sent_requests)] == [ADMIN_ID, OTHER_ADMIN_ID]
    assert caplog.text.count("chat not found") == 2


async def test_startup_logs_a_failure_of_the_global_texts_and_goes_on(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    session_factory: async_sessionmaker[AsyncSession],
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await session.execute(insert(User).values(tg_id=ADMIN_ID, role="user", language="uk"))

    async def make_request(_bot: Bot, method: TelegramMethod[Any], **_kwargs: Any) -> None:
        sent_requests.append(method)
        if isinstance(method, SetMyDescription):
            raise TelegramBadRequest(method, "Bad Request: description is too long")

    monkeypatch.setattr(bot.session, "make_request", make_request)

    with caplog.at_level(logging.WARNING):
        await publish_commands(session_factory, frozenset({ADMIN_ID}), bot)

    assert "description is too long" in caplog.text
    assert chat_menus(sent_requests) == [(ADMIN_ID, build_commands(UK, is_admin=True))]


@pytest.mark.parametrize(
    ("language", "texts"), [("en", EN), ("uk", UK), ("ru", RU)], ids=["en", "uk", "ru"]
)
async def test_user_menu_is_set_for_their_chat_in_their_language(
    bot: Bot, sent_requests: list[TelegramMethod[Any]], language: Language, texts: Texts
) -> None:
    await set_user_commands(bot, ADMIN_ID, language)

    assert chat_menus(sent_requests) == [(ADMIN_ID, build_commands(texts))]


async def test_user_menu_error_is_logged_not_raised(
    bot: Bot,
    sent_requests: list[TelegramMethod[Any]],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fail_chat_menus(bot, sent_requests, monkeypatch)

    with caplog.at_level(logging.WARNING):
        await set_user_commands(bot, ADMIN_ID, "uk")

    assert "chat not found" in caplog.text
