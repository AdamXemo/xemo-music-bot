"""A tap on a track: download it, send it as audio, and show progress on its button."""

import html
import logging
from typing import Final

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.utils.chat_action import ChatActionSender

from xemo_music_bot import timing
from xemo_music_bot.bot import emoji
from xemo_music_bot.bot.handlers.edits import edit_tapped_message, expire_results
from xemo_music_bot.bot.keyboards.results import TrackCallback, results_keyboard
from xemo_music_bot.bot.labels import format_duration, track_name
from xemo_music_bot.bot.locales import Texts
from xemo_music_bot.core.models import DownloadedAudio, Track
from xemo_music_bot.core.services.delivery import DeliveryService
from xemo_music_bot.core.services.search import SearchService, SearchSessionExpiredError
from xemo_music_bot.db.models import User
from xemo_music_bot.providers.base import PreviewOnlyError, ProviderError, TooLargeError

logger = logging.getLogger(__name__)

# Telegram shows a chat action for about 5 s, so a shorter interval keeps it unbroken.
_ACTION_INTERVAL: Final = 4


async def handle_track(
    callback: CallbackQuery,
    callback_data: TrackCallback,
    bot: Bot,
    db_user: User,
    texts: Texts,
    search_service: SearchService,
    delivery_service: DeliveryService,
) -> None:
    """Send the tapped track as an audio message, with its button showing the progress.

    Args:
        callback: The tap on a track button.
        callback_data: The parsed button data.
        bot: The bot, injected by aiogram.
        db_user: The sender's row, injected by ``AccessMiddleware``.
        texts: The user's catalog, injected by ``AccessMiddleware``.
        search_service: The long-lived service from the dispatcher's workflow data.
        delivery_service: The long-lived service from the dispatcher's workflow data.
    """
    session_id, index = callback_data.session_id, callback_data.index
    try:
        track = await search_service.start_loading(db_user.tg_id, session_id, index)
    except SearchSessionExpiredError:
        await expire_results(callback, texts)
        return
    if track is None:
        await callback.answer(texts.already_loading)
        return
    if delivery_service.is_too_long(track):
        # The claim was only needed to learn the track; nothing is downloading.
        await search_service.finish_loading(session_id, index)
        alert = texts.too_long.format(duration=format_duration(track.duration))
        await callback.answer(alert, show_alert=True)
        return

    with timing.timed_task(f"deliver {track_name(track)}"):
        try:
            # Inside the try: an answer Telegram rejects (the query is too old) must still
            # release the claim.
            with timing.stage("buttons", detail="block"):
                await callback.answer()
                await _show_buttons(callback, db_user, texts, search_service, session_id)
            async with ChatActionSender.upload_document(
                chat_id=db_user.tg_id, bot=bot, interval=_ACTION_INTERVAL
            ):
                await _deliver(track, bot, db_user.tg_id, texts, delivery_service)
        finally:
            with timing.stage("buttons back", detail="block"):
                await search_service.finish_loading(session_id, index)
                await _show_buttons(callback, db_user, texts, search_service, session_id)


async def _deliver(
    track: Track, bot: Bot, chat_id: int, texts: Texts, delivery_service: DeliveryService
) -> None:
    """Send the audio, or the message that says why it could not be."""

    async def send(audio: DownloadedAudio) -> None:
        with timing.stage("upload", detail="block"):
            await bot.send_audio(
                chat_id,
                FSInputFile(audio.path),
                performer=track.artist or None,
                title=track.title,
                duration=audio.duration,
                thumbnail=FSInputFile(audio.thumbnail),
            )

    name = html.escape(track_name(track), quote=False)
    try:
        await delivery_service.deliver(track, send)
    except TooLargeError:
        await bot.send_message(chat_id, texts.too_large.format(track=name))
    except PreviewOnlyError:
        text = texts.track_unavailable.format(track=name)
        await bot.send_message(chat_id, emoji.with_emoji(emoji.ERROR, text))
    except (ProviderError, TelegramAPIError):
        # Telegram refusing the upload is told to the user like any failed download.
        logger.warning("Delivery of %s failed", track.page_url, exc_info=True)
        text = texts.download_failed.format(track=name)
        await bot.send_message(chat_id, emoji.with_emoji(emoji.ERROR, text))


async def _show_buttons(
    callback: CallbackQuery,
    db_user: User,
    texts: Texts,
    search_service: SearchService,
    session_id: str,
) -> None:
    """Redraw the results buttons from the stored state: loading marks and current page.

    Best effort: the user may have deleted the message or the results may have expired,
    and neither is a reason to fail a delivery that already went out.
    """
    page = await search_service.current_page(db_user.tg_id, session_id)
    try:
        # Expired meanwhile: remove the buttons, as for any tap on dead results.
        keyboard = None if page is None else results_keyboard(page, texts)
        await edit_tapped_message(callback, None, keyboard)
    except TelegramAPIError:
        logger.debug("Could not redraw the results buttons", exc_info=True)


def build_router() -> Router:
    """Create the delivery router; include it before the catch-all fallback."""
    router = Router(name="delivery")
    router.callback_query.register(handle_track, TrackCallback.filter())
    return router
