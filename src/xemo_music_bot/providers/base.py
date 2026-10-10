"""The interface every music source implements."""

from typing import Protocol

from xemo_music_bot.core.models import Track


class ProviderError(Exception):
    """The music source failed or could not be reached."""


class MusicProvider(Protocol):
    """A source of tracks, such as SoundCloud.

    Implementations must not block the event loop: blocking work runs in a thread
    behind a concurrency limit.
    """

    async def search(self, query: str, limit: int) -> list[Track]:
        """Find tracks by name.

        Args:
            query: Free text, usually an artist and a track title.
            limit: Maximum number of tracks to return; must be at least 1.

        Returns:
            Up to ``limit`` tracks in the source's relevance order; empty if nothing
            matches.

        Raises:
            ProviderError: If the source fails or cannot be reached.
        """
        ...
