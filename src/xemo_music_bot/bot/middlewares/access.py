"""Let only members and config admins reach the handlers (ADR 0003)."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import Chat, Message, TelegramObject, Update, User
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.bot.invite_notice import notify_inviter
from xemo_music_bot.bot.locales import Language, detect_language, get_texts
from xemo_music_bot.core.services.access import AccessService, AccessStatus
from xemo_music_bot.core.services.invites import InviteService, JoinStatus
from xemo_music_bot.db.repositories.invites import InvitesRepository
from xemo_music_bot.db.repositories.users import UsersRepository


class AccessMiddleware(BaseMiddleware):
    """Drop updates from strangers, blocked users and non-private chats.

    Runs as an outer update middleware after ``DbSessionMiddleware``, whose session it
    uses. Allowed updates reach the handlers with ``db_user`` (the sender's row),
    ``is_admin`` and ``texts`` (the catalog for the row's language) in the handler data.
    A stranger's `/start <code>` with a working code joins them first, so it reaches the
    `/start` handler as a member's. Everything else is denied by default: the only replies
    are ``invite_invalid`` to a stranger's `/start` with any other payload and the
    "private bot" line to a stranger's plain `/start` or a blocked user's `/start`, and a
    denied callback query is answered without text.

    Args:
        admin_ids: Telegram IDs from config, the only source of admin rights.
    """

    def __init__(self, admin_ids: frozenset[int]) -> None:
        self._admin_ids = admin_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Call the handler only for an allowed sender in a private chat."""
        # aiogram's UserContextMiddleware runs earlier and fills these keys.
        sender: User | None = data.get("event_from_user")
        chat: Chat | None = data.get("event_chat")
        if sender is None:
            return None
        # The bot lives in private chats only, for members and admins too. Checked before
        # any query, so group traffic costs no database round trip.
        if chat is not None and chat.type != ChatType.PRIVATE:
            await _answer_callback(event)
            return None

        users = UsersRepository(data["session"])
        service = AccessService(users, self._admin_ids)
        language = detect_language(sender.language_code)
        access = await service.check(sender.id, sender.username, language)
        start = _start_message(event)
        payload = _start_payload(start) if start is not None else ""
        if access.status is AccessStatus.STRANGER and start is not None and payload:
            if not await _join(payload, sender, language, users, data):
                await start.answer(get_texts(language).invite_invalid)
                return None
            access = await service.check(sender.id, sender.username, language)
        # An allowed access always has a row; the `is None` check narrows the type for mypy.
        if not access.allowed or access.user is None:
            await _answer_callback(event)
            if start is not None:
                await start.answer(get_texts(language).private_bot)
            return None

        data["db_user"] = access.user
        data["is_admin"] = access.status is AccessStatus.ADMIN
        # The stored language, not Telegram's: the user may have picked another one.
        data["texts"] = get_texts(access.user.language)
        return await handler(event, data)


async def _join(
    code: str, sender: User, language: Language, users: UsersRepository, data: dict[str, Any]
) -> bool:
    """Join a stranger with ``code`` and notify the inviter; return whether they are in."""
    session: AsyncSession = data["session"]
    service = InviteService(InvitesRepository(session), users)
    result = await service.join(code, sender.id, sender.username, language)
    if result.status is JoinStatus.INVALID:
        return False
    # Set only when this update created the row.
    if result.inviter_id is not None:
        # Committed before the notice, so a join that is later rolled back is never
        # announced; DbSessionMiddleware commits the rest of the update separately.
        await session.commit()
        await notify_inviter(data["bot"], session, result.inviter_id, sender)
    return True


async def _answer_callback(event: TelegramObject) -> None:
    """Answer a denied callback query without text, so an old button stops spinning."""
    if isinstance(event, Update) and event.callback_query is not None:
        await event.callback_query.answer()


def _start_message(event: TelegramObject) -> Message | None:
    """Return the update's message if it is `/start` or `/start@botname`, payload or not."""
    if not isinstance(event, Update) or event.message is None or not event.message.text:
        return None
    # Whitespace-only text (a lone non-breaking space, say) splits into no parts at all.
    parts = event.message.text.split(maxsplit=1)
    if not parts or parts[0].split("@", maxsplit=1)[0] != "/start":
        return None
    return event.message


def _start_payload(message: Message) -> str:
    """Return the text after `/start`, or an empty string if there is none."""
    parts = (message.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""
