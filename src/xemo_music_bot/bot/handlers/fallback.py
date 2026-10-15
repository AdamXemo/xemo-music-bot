"""Catch-all for button taps that no feature router recognises."""

from aiogram import Router
from aiogram.types import CallbackQuery

from xemo_music_bot.bot.handlers.edits import edit_tapped_message


async def handle_unrecognised_button(callback: CallbackQuery) -> None:
    """Answer the tap without text and remove the message's dead buttons.

    Covers buttons from older versions of the bot and forged callback data, so no tap is
    left spinning (MVP spec: every callback is answered). Nothing is saved.

    Args:
        callback: A tap no other handler matched.
    """
    await callback.answer()
    await edit_tapped_message(callback, None)


def build_router() -> Router:
    """Create the fallback router; the dispatcher must include it after every other router."""
    router = Router(name="fallback")
    router.callback_query.register(handle_unrecognised_button)
    return router
