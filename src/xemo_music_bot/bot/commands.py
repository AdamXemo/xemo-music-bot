"""The bot's command menu and profile texts, kept in the user's language (MVP spec, Commands)."""

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from xemo_music_bot.bot.locales import DEFAULT_LANGUAGE, LANGUAGES, Language, Texts, get_texts
from xemo_music_bot.core.services.language import LanguageService
from xemo_music_bot.db.repositories.users import UsersRepository

logger = logging.getLogger(__name__)


def build_commands(texts: Texts, *, is_admin: bool = False) -> list[BotCommand]:
    """Return the command menu in the catalog's language.

    Only commands that exist are listed; later roadmap items add theirs.

    Args:
        texts: The catalog for the menu's language.
        is_admin: Whether to add the admin commands, for a config admin's chat menu.
    """
    commands = [
        BotCommand(command="start", description=texts.cmd_start),
        BotCommand(command="language", description=texts.cmd_language),
    ]
    if is_admin:
        commands.append(BotCommand(command="invite", description=texts.cmd_invite))
    return commands


async def set_user_commands(
    bot: Bot, tg_id: int, language: Language, *, is_admin: bool = False
) -> None:
    """Show the user the command menu in ``language``, whatever their Telegram app speaks.

    A failure is logged, not raised: a missing menu must not break the caller.

    Args:
        bot: The bot to call Telegram with.
        tg_id: Telegram user ID; equal to the chat ID of their private chat.
        language: The user's bot language.
        is_admin: Whether the user is a config admin, who also gets the admin commands.
    """
    commands = build_commands(get_texts(language), is_admin=is_admin)
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=tg_id))
    except TelegramAPIError as error:
        logger.warning("Could not set the command menu for user %d: %s", tg_id, error)


async def publish_commands(
    session_factory: async_sessionmaker[AsyncSession], admin_ids: frozenset[int], bot: Bot
) -> None:
    """Startup hook: publish the menu and descriptions, then the admins' chat menus.

    The default (no language) entries are English, for clients in other languages. A
    Telegram failure is logged and startup goes on; the bot works without these.

    Args:
        session_factory: Opens the session to read the admins' stored languages.
        admin_ids: Telegram IDs from config with admin rights.
        bot: The bot to call Telegram with.
    """
    try:
        # `None` is the default entry Telegram falls back to; the others match the client.
        for language_code in (None, *LANGUAGES):
            texts = get_texts(language_code or DEFAULT_LANGUAGE)
            await bot.set_my_commands(build_commands(texts), language_code=language_code)
            await bot.set_my_description(texts.bot_description, language_code=language_code)
            await bot.set_my_short_description(
                texts.bot_short_description, language_code=language_code
            )
    except TelegramAPIError as error:
        logger.warning("Could not publish the bot's commands and descriptions: %s", error)
    async with session_factory() as session:
        languages = await LanguageService(UsersRepository(session)).get_languages(admin_ids)
    # Admins who never sent an update have no row yet and no chat for Telegram to find.
    for tg_id, language in languages.items():
        await set_user_commands(bot, tg_id, language, is_admin=True)
