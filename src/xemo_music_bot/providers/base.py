"""The interface every music source implements."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from xemo_music_bot.core.models import DownloadedAudio, Track


class ProviderError(Exception):
    """The music source failed or could not be reached."""


class TooLongError(ProviderError):
    """The track is too long to fit Telegram's upload limit; nothing was downloaded."""


class TooLargeError(ProviderError):
    """The downloaded file is over Telegram's upload limit."""


class PreviewOnlyError(ProviderError):
    """The source offers only a short preview (SoundCloud Go+) or a locked stream."""


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

    def download(self, track: Track) -> AbstractAsyncContextManager[DownloadedAudio]:
        """Download a track as an MP3 that fits Telegram's upload limit.

        Use it as ``async with provider.download(track) as audio:``. The audio file
        lives in a temporary directory that is removed when the block exits, however it
        exits, so a caller cannot leak files and audio is never kept after the upload.

        Args:
            track: The track to fetch, as returned by ``search``.

        Returns:
            An async context manager that yields the downloaded audio.

        Raises:
            TooLongError: If the track is too long to fit, checked before downloading.
            TooLargeError: If the downloaded file is over the limit.
            PreviewOnlyError: If the source only offers a preview of the track.
            ProviderError: If the download fails, times out or the source is unreachable.
        """
        ...
