"""Let only members and config admins reach the handlers (ADR 0003)."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import Chat, TelegramObject, Update, User

from xemo_music_bot.bot.locales import detect_language, get_texts
from xemo_music_bot.core.services.access import AccessService, AccessStatus
from xemo_music_bot.db.repositories.users import UsersRepository


class AccessMiddleware(BaseMiddleware):
    """Drop updates from strangers, blocked users and non-private chats.

    Runs as an outer update middleware after ``DbSessionMiddleware``, whose session it
    uses. Allowed updates reach the handlers with ``db_user`` (the sender's row),
    ``is_admin`` and ``texts`` (the catalog for the row's language) in the handler data.
    Everything else is denied by default: the only reply is the "private bot" line to a
    stranger's or blocked user's ``/start``.

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
            return None

        service = AccessService(UsersRepository(data["session"]), self._admin_ids)
        access = await service.check(
            sender.id, sender.username, detect_language(sender.language_code)
        )
        # An allowed access always has a row; the `is None` check narrows the type for mypy.
        if not access.allowed or access.user is None:
            await _reply_private_bot_to_start(event, sender)
            return None

        data["db_user"] = access.user
        data["is_admin"] = access.status is AccessStatus.ADMIN
        # The stored language, not Telegram's: the user may have picked another one.
        data["texts"] = get_texts(access.user.language)
        return await handler(event, data)


async def _reply_private_bot_to_start(event: TelegramObject, sender: User) -> None:
    """Send the "private bot" line if the update is a `/start` message, else nothing."""
    if not isinstance(event, Update) or event.message is None:
        return
    if not _is_start_command(event.message.text):
        return
    texts = get_texts(detect_language(sender.language_code))
    await event.message.answer(texts.private_bot)


def _is_start_command(text: str | None) -> bool:
    """Whether ``text`` is `/start`, `/start@botname` or either with a payload."""
    if not text:
        return False
    # Whitespace-only text (a lone non-breaking space, say) splits into no parts at all.
    parts = text.split(maxsplit=1)
    return bool(parts) and parts[0].split("@", maxsplit=1)[0] == "/start"
