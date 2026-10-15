"""Search by text message, the results message's buttons, and replies to everything else."""

import html
import logging
import re
from typing import Final

from aiogram import Bot, F, Router
from aiogram.enums import ContentType, MessageEntityType
from aiogram.types import CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from xemo_music_bot.bot.handlers.edits import edit_tapped_message, expire_results
from xemo_music_bot.bot.keyboards.results import PageCallback, results_keyboard
from xemo_music_bot.bot.locales import Texts
from xemo_music_bot.core.services.search import SearchPage, SearchService
from xemo_music_bot.db.models import User
from xemo_music_bot.providers.base import ProviderError

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH: Final = 100
_LINK_ENTITIES: Final = frozenset({MessageEntityType.URL, MessageEntityType.TEXT_LINK})
# Telegram marks most links itself; this catches a scheme it did not (e.g. in a forward).
_LINK_PATTERN: Final = re.compile(r"https?://", re.IGNORECASE)


def results_text(page: SearchPage, texts: Texts) -> str:
    """Return the results message's text: the query, escaped, in bold."""
    return texts.results_header.format(query=html.escape(page.query, quote=False))


def _has_link(message: Message, text: str) -> bool:
    entities = message.entities or []
    return any(entity.type in _LINK_ENTITIES for entity in entities) or bool(
        _LINK_PATTERN.search(text)
    )


async def handle_text(
    message: Message,
    db_user: User,
    texts: Texts,
    search_service: SearchService,
    bot: Bot,
) -> None:
    """Search for a plain text message and reply with the results or the reason for none.

    Args:
        message: A text message that is not a command.
        db_user: The sender's row, injected by ``AccessMiddleware``.
        texts: The user's catalog, injected by ``AccessMiddleware``.
        search_service: The long-lived service from the dispatcher's workflow data.
        bot: The bot, injected by aiogram.
    """
    query = (message.text or "").strip()
    if not query:
        return
    if _has_link(message, query):
        await message.answer(texts.link_not_supported)
        return
    if len(query) > MAX_QUERY_LENGTH:
        await message.answer(texts.query_too_long)
        return

    # The action runs until the reply is sent, so the chat shows "typing" for the whole wait.
    async with ChatActionSender.typing(chat_id=message.chat.id, bot=bot):
        try:
            page = await search_service.search(db_user.tg_id, query)
        except ProviderError:
            logger.warning("Search failed", exc_info=True)
            await message.answer(texts.search_failed)
            return
        if page is None:
            await message.answer(texts.no_results.format(query=html.escape(query, quote=False)))
            return
        await message.answer(results_text(page, texts), reply_markup=results_keyboard(page, texts))


async def handle_not_text(message: Message, texts: Texts) -> None:
    """Ask for the track name as text (sticker, voice, photo, file and so on)."""
    await message.answer(texts.not_text)


async def handle_unknown_command(message: Message, texts: Texts) -> None:
    """Reply to a command no earlier router handled."""
    await message.answer(texts.unknown_command)


async def handle_page(
    callback: CallbackQuery,
    callback_data: PageCallback,
    db_user: User,
    texts: Texts,
    search_service: SearchService,
) -> None:
    """Turn the results message to another page by editing it in place.

    Args:
        callback: The tap on an enabled pager arrow.
        callback_data: The parsed button data.
        db_user: The sender's row, injected by ``AccessMiddleware``.
        texts: The user's catalog, injected by ``AccessMiddleware``.
        search_service: The long-lived service from the dispatcher's workflow data.
    """
    page = await search_service.get_page(
        db_user.tg_id, callback_data.session_id, callback_data.page
    )
    if page is None:
        await expire_results(callback, texts)
        return
    await callback.answer()
    await edit_tapped_message(callback, results_text(page, texts), results_keyboard(page, texts))


# Content a user sends on purpose. Service messages (a pin, an auto-delete timer, a chat
# background) are not the user talking to the bot, so they get no reply.
_USER_CONTENT: Final = frozenset(
    {
        ContentType.STICKER,
        ContentType.VOICE,
        ContentType.VIDEO_NOTE,
        ContentType.VIDEO,
        ContentType.PHOTO,
        ContentType.AUDIO,
        ContentType.DOCUMENT,
        ContentType.ANIMATION,
        ContentType.CONTACT,
        ContentType.LOCATION,
        ContentType.VENUE,
        ContentType.POLL,
        ContentType.DICE,
    }
)


def build_router() -> Router:
    """Create the search router.

    The dispatcher must include it after the command routers: the unknown-command and
    text handlers match any text, so they would otherwise shadow `/start` and
    `/language`.
    """
    router = Router(name="search")
    router.message.register(handle_unknown_command, F.text.startswith("/"))
    router.message.register(handle_text, F.text)
    router.message.register(handle_not_text, F.content_type.in_(_USER_CONTENT))
    router.callback_query.register(handle_page, PageCallback.filter())
    return router
