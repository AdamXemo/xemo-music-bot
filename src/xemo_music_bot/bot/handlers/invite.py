"""`/invite` for config admins: a new single-use code and its link."""

from aiogram import Bot, F, Router
from aiogram.filters import Command, MagicData
from aiogram.types import LinkPreviewOptions, Message
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.bot.keyboards.invite import invite_keyboard
from xemo_music_bot.bot.locales import Texts, plural
from xemo_music_bot.core.services.invites import INVITE_TTL, InviteService
from xemo_music_bot.db.models import User
from xemo_music_bot.db.repositories.invites import InvitesRepository
from xemo_music_bot.db.repositories.users import UsersRepository


async def handle_invite(
    message: Message, db_user: User, texts: Texts, session: AsyncSession, bot: Bot
) -> None:
    """Create a code and reply with its link, how long it works, and Copy and Share.

    Args:
        message: The `/invite` message; any text after the command is ignored.
        db_user: The admin's row, injected by ``AccessMiddleware``.
        texts: The admin's catalog, injected by ``AccessMiddleware``.
        session: The update's session, injected by ``DbSessionMiddleware``.
        bot: The bot, injected by aiogram.
    """
    service = InviteService(InvitesRepository(session), UsersRepository(session))
    invite = await service.create(db_user.tg_id)
    # Bot.me() calls getMe once and caches the answer on the bot.
    me = await bot.me()
    # Shown without the scheme; Telegram still makes it a link.
    link = f"t.me/{me.username}?start={invite.code}"
    days = plural(db_user.language, INVITE_TTL.days, texts.invite_days)
    await message.answer(
        texts.invite_created.format(link=link, days=days),
        reply_markup=invite_keyboard(f"https://{link}", texts),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


def build_router() -> Router:
    """Create the `/invite` router (see ``start.build_router`` for why it is a factory).

    A member's `/invite` matches nothing here and reaches the search router's
    unknown-command reply, like any command they do not have.
    """
    router = Router(name="invite")
    # `is_admin` is set by AccessMiddleware; MagicData reads it from the handler data.
    router.message.register(handle_invite, Command("invite"), MagicData(F.is_admin))
    return router
