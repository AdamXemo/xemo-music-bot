"""The notice the inviter gets when a friend joins with their code."""

import html
import logging
from typing import Final

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.bot.labels import shorten
from xemo_music_bot.bot.locales import DEFAULT_LANGUAGE, Texts, get_texts
from xemo_music_bot.core.services.language import LanguageService
from xemo_music_bot.db.repositories.users import UsersRepository

logger = logging.getLogger(__name__)

# Longest friend's name in the join notice (spec, "Name in the notice").
MAX_NAME_WIDTH: Final = 40


def friend_text(friend: TelegramUser, texts: Texts) -> str:
    """Return the friend as the join notice shows them: the name, then the @username.

    Args:
        friend: The Telegram user who joined.
        texts: The inviter's catalog.

    Returns:
        HTML: the name on one line, cut to ``MAX_NAME_WIDTH`` and escaped.
    """
    name = " ".join(friend.full_name.splitlines())
    name = html.escape(shorten(name, MAX_NAME_WIDTH), quote=False)
    if friend.username is None:
        return name
    return texts.invite_friend.format(name=name, username=friend.username)


async def notify_inviter(
    bot: Bot, session: AsyncSession, inviter_id: int, friend: TelegramUser
) -> None:
    """Tell the inviter, in their own language, that ``friend`` joined with their code.

    Call it only after the join is committed. A failed send (say the inviter blocked the
    bot) is logged, not raised: the join stands either way.

    Args:
        bot: The bot to send with.
        session: The update's session, to read the inviter's language.
        inviter_id: Telegram ID of the code's creator.
        friend: The Telegram user who joined.
    """
    languages = await LanguageService(UsersRepository(session)).get_languages([inviter_id])
    texts = get_texts(languages.get(inviter_id, DEFAULT_LANGUAGE))
    text = texts.invite_joined.format(friend=friend_text(friend, texts))
    try:
        await bot.send_message(inviter_id, text)
    except TelegramAPIError as error:
        logger.warning("Could not tell user %d that their invite was used: %s", inviter_id, error)
