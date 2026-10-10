"""SoundCloud search through yt-dlp (ADR 0002)."""

import asyncio
import logging
from collections.abc import Callable, Mapping
from typing import Any, Final

from yt_dlp import YoutubeDL
from yt_dlp.utils import YoutubeDLError

from xemo_music_bot.core.metadata import clean_track_name
from xemo_music_bot.core.models import Track
from xemo_music_bot.providers.base import ProviderError

logger = logging.getLogger(__name__)

PROVIDER_NAME: Final = "soundcloud"

# Blocking call that runs yt-dlp on a URL or search key and returns its info dict.
type Extractor = Callable[[str], Mapping[str, Any]]

# yt-dlp lists every size SoundCloud serves; 500x500 is the smallest JPEG at or above
# Telegram's 320x320 audio thumbnail, so delivery only has to scale it down.
_ARTWORK_ID: Final = "t500x500"

_SEARCH_OPTIONS: Final[Mapping[str, Any]] = {
    # Search entries already carry title, uploader, duration and artwork. Resolving each
    # entry would cost several more requests per track and add nothing search needs.
    "extract_flat": "in_playlist",
    "skip_download": True,
    "noprogress": True,
    "socket_timeout": 10,
    # Send yt-dlp's output through our logging instead of stdout and stderr.
    "logger": logging.getLogger("yt_dlp"),
}


def extract_with_yt_dlp(url: str) -> Mapping[str, Any]:
    """Run a metadata-only yt-dlp extraction. Blocks; call it from a worker thread.

    Args:
        url: A URL or yt-dlp search key such as ``scsearch5:daft punk``.

    Returns:
        The yt-dlp info dict; search results are under ``entries``.

    Raises:
        YoutubeDLError: If extraction fails.
    """
    # A YoutubeDL instance keeps per-run state, so each call gets its own.
    with YoutubeDL(dict(_SEARCH_OPTIONS)) as ydl:
        info: Mapping[str, Any] = ydl.extract_info(url, download=False)
    return info


class SoundCloudProvider:
    """Finds tracks on SoundCloud; implements ``MusicProvider``.

    Args:
        extractor: Blocking yt-dlp call; tests pass a fake so no network is used.
        max_concurrency: How many searches may run yt-dlp at the same time.
    """

    def __init__(
        self, extractor: Extractor = extract_with_yt_dlp, max_concurrency: int = 4
    ) -> None:
        self._extract = extractor
        # Each running search holds a worker thread; the cap keeps a burst of searches
        # from taking over the thread pool that downloads will share.
        self._slots = asyncio.Semaphore(max_concurrency)

    async def search(self, query: str, limit: int) -> list[Track]:
        """Find up to ``limit`` SoundCloud tracks matching ``query``.

        Raises:
            ValueError: If ``limit`` is less than 1.
            ProviderError: If yt-dlp fails, for example when SoundCloud is unreachable.
        """
        if limit < 1:
            raise ValueError(f"limit must be at least 1, got {limit}")
        query = " ".join(query.split())
        if not query:
            return []

        async with self._slots:
            try:
                info = await asyncio.to_thread(self._extract, f"scsearch{limit}:{query}")
            except YoutubeDLError as exc:
                raise ProviderError(f"SoundCloud search failed: {exc}") from exc

        entries: list[Mapping[str, Any]] = info.get("entries") or []
        return [track for entry in entries if (track := _to_track(entry)) is not None]


def _to_track(entry: Mapping[str, Any]) -> Track | None:
    """Map a flat yt-dlp search entry to a ``Track``, or ``None`` if it is unusable."""
    track_id = entry.get("id")
    raw_title = entry.get("title")
    duration = entry.get("duration")
    page_url = entry.get("webpage_url")
    uploader = entry.get("uploader")
    if not (
        isinstance(track_id, str)
        and isinstance(raw_title, str)
        and isinstance(duration, int | float)
        and isinstance(page_url, str)
    ):
        logger.debug("Skipping SoundCloud entry %r: missing required fields", track_id)
        return None

    name = clean_track_name(raw_title, uploader if isinstance(uploader, str) else "")
    if not name.title:
        logger.debug("Skipping SoundCloud entry %r: empty title", track_id)
        return None
    return Track(
        provider=PROVIDER_NAME,
        provider_track_id=track_id,
        title=name.title,
        artist=name.artist,
        duration=round(duration),
        artwork_url=_artwork_url(entry),
        page_url=page_url,
    )


def _artwork_url(entry: Mapping[str, Any]) -> str | None:
    """Pick the cover URL from an entry's thumbnails.

    yt-dlp already falls back to the uploader's avatar when a track has no artwork. A
    URL without SoundCloud's size suffix comes as a single thumbnail without an ``id``.
    """
    urls = {thumb.get("id"): thumb.get("url") for thumb in entry.get("thumbnails") or []}
    return urls.get(_ARTWORK_ID) or next((url for url in urls.values() if url), None)
