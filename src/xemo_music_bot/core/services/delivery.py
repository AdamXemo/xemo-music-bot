"""Get a track's audio and hand it to the caller to send (feature spec: "Delivery")."""

import logging
from collections.abc import Awaitable, Callable

from xemo_music_bot.core.models import DownloadedAudio, Track
from xemo_music_bot.db.repositories.tracks import TracksRepository
from xemo_music_bot.providers.base import MusicProvider

logger = logging.getLogger(__name__)


class StaleFileIdError(Exception):
    """Telegram rejected a stored ``file_id``; raised by the caller's send-by-id callback."""


class DeliveryService:
    """Sends a track Telegram already holds by its ``file_id``, else downloads it.

    The caller owns the sending (``core`` knows nothing of Telegram), so ``send``
    callbacks take a stored ``file_id``, or the audio while its temp files still exist.
    A ``file_id`` is an opaque string here.

    Args:
        provider: The music source to download from.
        tracks: The ``file_id`` cache.
        max_duration: Longest track in seconds the provider can deliver within the upload
            limit; longer tracks are refused before anything is claimed or downloaded.
    """

    def __init__(
        self, provider: MusicProvider, tracks: TracksRepository, max_duration: int
    ) -> None:
        self._provider = provider
        self._tracks = tracks
        self._max_duration = max_duration

    def is_too_long(self, track: Track) -> bool:
        """Tell whether the track is too long to deliver, so the user can be told up front."""
        return track.duration > self._max_duration

    async def send_cached(self, track: Track, send: Callable[[str], Awaitable[None]]) -> bool:
        """Send the track by its stored ``file_id``, if there is one Telegram still accepts.

        Args:
            track: The track to deliver, as returned by a search.
            send: Sends the audio by ``file_id``; raises ``StaleFileIdError`` if Telegram
                rejects the id.

        Returns:
            Whether the audio was sent. ``False`` means a download is needed: the track
            was never sent, or its ``file_id`` was stale and is now forgotten.

        Raises:
            Exception: Whatever ``send`` raises other than ``StaleFileIdError``, unchanged;
                the stored ``file_id`` is kept then.
        """
        file_id = await self._tracks.get_file_id(track)
        if file_id is None:
            return False
        try:
            await send(file_id)
        except StaleFileIdError:
            await self._tracks.delete_stale(track, file_id)
            logger.info("Stored file_id of %s was rejected, downloading again", track.page_url)
            return False
        return True

    async def deliver(
        self, track: Track, send: Callable[[DownloadedAudio], Awaitable[str | None]]
    ) -> None:
        """Download the track, pass the audio to ``send`` and remember the ``file_id``.

        Args:
            track: The track to deliver, as returned by a search.
            send: Uploads the audio and returns the ``file_id`` Telegram gave it, or
                ``None`` if there is none; it must finish with the files before it returns.

        Raises:
            ProviderError: The download failed; ``TooLargeError`` and ``PreviewOnlyError``
                say why for the two cases the user is told about.
            Exception: Whatever ``send`` raises, unchanged; nothing is stored then.
        """
        async with self._provider.download(track) as audio:
            file_id = await send(audio)
        if file_id is None:
            return
        try:
            await self._tracks.save(track, file_id)
        except Exception:
            # The user already has the audio; a lost save only costs the next tap a
            # download. Broad on purpose: core does not know the database's errors.
            logger.warning("Could not cache the file_id of %s", track.page_url, exc_info=True)
