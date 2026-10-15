"""The results message's buttons: one per track, then the pager row."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import DisabledButton, InlineKeyboardButton, InlineKeyboardMarkup

from xemo_music_bot.bot import emoji
from xemo_music_bot.bot.labels import result_label
from xemo_music_bot.bot.locales import Texts
from xemo_music_bot.core.models import Track
from xemo_music_bot.core.services.search import SearchPage


class TrackCallback(CallbackData, prefix="track"):
    """A track button. Packs to ``track:<session_id>:<index>``, about 30 bytes of the 64.

    Attributes:
        session_id: The search session the track belongs to.
        index: The track's index across all pages of the session.
    """

    session_id: str
    index: int


class PageCallback(CallbackData, prefix="page"):
    """An enabled pager arrow. Packs to ``page:<session_id>:<page>``.

    Attributes:
        session_id: The search session to turn.
        page: The wanted page, counting from 0.
    """

    session_id: str
    page: int


def results_keyboard(page: SearchPage, texts: Texts) -> InlineKeyboardMarkup:
    """Build the buttons for one page of results.

    A track that is downloading shows a disabled loading button instead of its label.
    The pager row exists only when there is more than one page. An arrow at either end is
    a disabled button rather than a missing one, so the row never changes shape.

    Args:
        page: The page to render.
        texts: The user's catalog.
    """
    rows = [[_track_button(page, index, track, texts)] for index, track in page.items]
    if page.pages > 1:
        rows.append(_pager_row(page, texts))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _track_button(page: SearchPage, index: int, track: Track, texts: Texts) -> InlineKeyboardButton:
    if index in page.loading:
        return InlineKeyboardButton(
            text=texts.track_loading,
            icon_custom_emoji_id=emoji.button_icon(emoji.LOADING),
            disabled=DisabledButton(),
        )
    return InlineKeyboardButton(
        text=result_label(track),
        icon_custom_emoji_id=emoji.button_icon(emoji.TRACK),
        callback_data=TrackCallback(session_id=page.session_id, index=index).pack(),
    )


def _pager_row(page: SearchPage, texts: Texts) -> list[InlineKeyboardButton]:
    counter = texts.pager_counter.format(page=page.page + 1, pages=page.pages)
    return [
        _arrow(texts.pager_back, page, page.page - 1, enabled=page.page > 0),
        InlineKeyboardButton(text=counter, disabled=DisabledButton()),
        _arrow(texts.pager_next, page, page.page + 1, enabled=page.page < page.pages - 1),
    ]


def _arrow(text: str, page: SearchPage, target: int, *, enabled: bool) -> InlineKeyboardButton:
    if not enabled:
        return InlineKeyboardButton(text=text, disabled=DisabledButton())
    callback_data = PageCallback(session_id=page.session_id, page=target).pack()
    return InlineKeyboardButton(text=text, callback_data=callback_data)
