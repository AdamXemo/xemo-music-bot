"""Get a track's audio and hand it to the caller to send (feature spec: "Delivery")."""

from collections.abc import Awaitable, Callable

from xemo_music_bot.core.models import DownloadedAudio, Track
from xemo_music_bot.providers.base import MusicProvider


class DeliveryService:
    """Downloads a track and lets the caller send it before the file is deleted.

    The caller owns the sending (``core`` knows nothing of Telegram), so a ``send``
    callback takes the audio while its temp files still exist.

    Args:
        provider: The music source to download from.
        max_duration: Longest track in seconds the provider can deliver within the upload
            limit; longer tracks are refused before anything is claimed or downloaded.
    """

    def __init__(self, provider: MusicProvider, max_duration: int) -> None:
        self._provider = provider
        self._max_duration = max_duration

    def is_too_long(self, track: Track) -> bool:
        """Tell whether the track is too long to deliver, so the user can be told up front."""
        return track.duration > self._max_duration

    async def deliver(
        self, track: Track, send: Callable[[DownloadedAudio], Awaitable[None]]
    ) -> None:
        """Download the track and pass the audio to ``send``; the files go when it returns.

        Args:
            track: The track to deliver, as returned by a search.
            send: Uploads the audio; it must finish with the files before it returns.

        Raises:
            ProviderError: The download failed; ``TooLargeError`` and ``PreviewOnlyError``
                say why for the two cases the user is told about.
            Exception: Whatever ``send`` raises, unchanged.
        """
        async with self._provider.download(track) as audio:
            await send(audio)
