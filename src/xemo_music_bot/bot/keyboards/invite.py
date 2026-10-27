"""The Copy and Share buttons under an invite link."""

from urllib.parse import quote, urlencode

from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

from xemo_music_bot.bot.locales import Texts

_SHARE_URL = "https://t.me/share/url"


def invite_keyboard(link: str, texts: Texts) -> InlineKeyboardMarkup:
    """Return one row: Copy puts ``link`` on the clipboard, Share opens Telegram's chat picker.

    Neither button sends a callback, so there is nothing to answer.

    Args:
        link: The full ``https://`` invite link.
        texts: The admin's catalog.
    """
    # Spaces as %20: the default `quote_plus` writes "+", a space only in form encoding.
    query = urlencode({"url": link, "text": texts.invite_share_text}, quote_via=quote)
    copy = InlineKeyboardButton(text=texts.invite_copy, copy_text=CopyTextButton(text=link))
    share = InlineKeyboardButton(text=texts.invite_share, url=f"{_SHARE_URL}?{query}")
    return InlineKeyboardMarkup(inline_keyboard=[[copy, share]])
