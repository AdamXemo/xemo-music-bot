"""Editing the message under a tapped inline button, shared by the callback handlers."""

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


async def edit_tapped_message(
    callback: CallbackQuery, text: str | None, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    """Replace the text and buttons of the message under the tap.

    By default the buttons are removed and the text is replaced unless ``None``.

    Args:
        callback: The tap, already answered.
        text: The new message text (HTML), or ``None`` to keep the text as it is.
        reply_markup: The new buttons; none removes them. Only used together with ``text``.

    Raises:
        TelegramBadRequest: Telegram rejected the edit for a reason other than "message
            is not modified".
    """
    # A deleted message comes as InaccessibleMessage and cannot be edited; the tap is
    # already answered, so there is nothing left to do.
    if not isinstance(callback.message, Message):
        return
    try:
        if text is None:
            await callback.message.edit_reply_markup(reply_markup=None)
        else:
            # A text edit without `reply_markup` removes the inline keyboard as well.
            await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as error:
        # A double tap repeats an edit that is already applied; Telegram rejects it, and
        # the message already shows what the user asked for.
        if "message is not modified" not in error.message:
            raise
