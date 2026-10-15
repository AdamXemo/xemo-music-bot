"""Custom emoji slots (UX guide, "Emoji rules").

Specs name slots, never emoji IDs; the IDs live only here. Every slot stays ``None``
until the owner picks the premium custom emoji, and an empty slot renders nothing, so
each screen works without emoji.
"""

from dataclasses import dataclass
from typing import Final


@dataclass(slots=True, frozen=True)
class CustomEmoji:
    """A premium custom emoji.

    Attributes:
        emoji_id: Telegram's custom emoji ID.
        alt: The emoji's own regular emoji, which Telegram requires inside message text
            and shows where custom emoji cannot appear (notifications, the chat list).
    """

    emoji_id: str
    alt: str


HELLO: Final[CustomEmoji | None] = None
"""In front of the welcome text."""


def with_emoji(slot: CustomEmoji | None, html: str) -> str:
    """Put the slot's emoji in front of HTML message text.

    Args:
        slot: The slot to render; an empty slot leaves the text unchanged.
        html: Message text in HTML parse mode.

    Returns:
        The text, prefixed with a ``<tg-emoji>`` element if the slot is set.
    """
    if slot is None:
        return html
    return f'<tg-emoji emoji-id="{slot.emoji_id}">{slot.alt}</tg-emoji> {html}'
