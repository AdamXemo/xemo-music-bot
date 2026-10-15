"""SoundCloud search and download through yt-dlp (ADR 0002)."""

import asyncio
import contextlib
import logging
import shutil
import tempfile
import threading
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Final

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled, YoutubeDLError

from xemo_music_bot.core.metadata import clean_track_name
from xemo_music_bot.core.models import DownloadedAudio, Track
from xemo_music_bot.providers.base import (
    PreviewOnlyError,
    ProviderError,
    TooLargeError,
    TooLongError,
)

logger = logging.getLogger(__name__)

PROVIDER_NAME: Final = "soundcloud"

# Blocking call that runs yt-dlp on a URL or search key and returns its info dict.
type Extractor = Callable[[str], Mapping[str, Any]]

# Blocking call that downloads a URL into a directory as MP3 and returns yt-dlp's info
# dict. It must stop soon after the event is set (the download timed out).
type Downloader = Callable[[str, Path, threading.Event], Mapping[str, Any]]

# Telegram's limit for bot uploads is "50 MB"; the decimal reading is the safe one.
UPLOAD_LIMIT_BYTES: Final = 50_000_000

# Bitrate of MP3s that yt-dlp converts with ffmpeg. An MP3 stream is copied as is, and
# SoundCloud serves those at 128 kbps or less, so this is the largest output per second.
MP3_BITRATE_KBPS: Final = 192

# Longest track whose MP3 is sure to fit the upload limit (about 34 minutes).
MAX_DURATION: Final = UPLOAD_LIMIT_BYTES * 8 // (MP3_BITRATE_KBPS * 1000)

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


def download_with_yt_dlp(url: str, directory: Path, cancel: threading.Event) -> Mapping[str, Any]:
    """Download a track as MP3 into ``directory``. Blocks; call it from a worker thread.

    Args:
        url: The track's page URL.
        directory: Where the audio file is written.
        cancel: When set, the download stops at the next progress update or before the
            next post-processing step; a request in flight is not interrupted.

    Returns:
        The yt-dlp info dict; the final file is in ``requested_downloads``.

    Raises:
        YoutubeDLError: If extraction, download or conversion fails or is cancelled.
    """

    def stop_if_cancelled(_progress: Mapping[str, Any]) -> None:
        if cancel.is_set():
            raise DownloadCancelled

    options: dict[str, Any] = {
        # Prefer SoundCloud's own MP3 (copied, no re-encoding). Previews rank last, so
        # one is picked only when nothing else exists, and then it is rejected by name.
        "format": "bestaudio[ext=mp3][format_id!*=preview]/bestaudio[format_id!*=preview]"
        "/bestaudio",
        # Anything that is not MP3 (SoundCloud's HLS AAC and Opus) is converted.
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(MP3_BITRATE_KBPS),
            }
        ],
        "outtmpl": str(directory / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "noprogress": True,
        "progress_hooks": [stop_if_cancelled],
        # Also checked before each post-processing step, so a timeout skips ffmpeg.
        "postprocessor_hooks": [stop_if_cancelled],
        "socket_timeout": 15,
        "retries": 2,
        "fragment_retries": 2,
        "logger": logging.getLogger("yt_dlp"),
    }
    with YoutubeDL(options) as ydl:
        info: Mapping[str, Any] = ydl.extract_info(url, download=True)
    return info


class SoundCloudProvider:
    """Finds and downloads SoundCloud tracks; implements ``MusicProvider``.

    Args:
        extractor: Blocking yt-dlp search call; tests pass a fake so no network is used.
        max_concurrency: How many searches may run yt-dlp at the same time.
        downloader: Blocking yt-dlp download call; tests pass a fake.
        max_downloads: How many downloads may run at the same time.
        download_timeout: Seconds a download may run, once it has a slot, before its
            worker is told to stop (see ``_run_download`` for what that bounds).
    """

    def __init__(
        self,
        extractor: Extractor = extract_with_yt_dlp,
        max_concurrency: int = 4,
        downloader: Downloader = download_with_yt_dlp,
        max_downloads: int = 2,
        download_timeout: float = 180,
    ) -> None:
        self._extract = extractor
        # Each running search holds a worker thread; the cap keeps a burst of searches
        # from taking over the thread pool that downloads share.
        self._slots = asyncio.Semaphore(max_concurrency)
        self._download = downloader
        # Downloads get their own, smaller limit: they are heavier (bandwidth, ffmpeg)
        # and must not queue behind searches, nor searches behind them.
        self._download_slots = asyncio.Semaphore(max_downloads)
        self._download_timeout = download_timeout

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
            except (YoutubeDLError, OSError) as exc:
                raise ProviderError(f"SoundCloud search failed: {exc}") from exc

        entries: list[Mapping[str, Any]] = info.get("entries") or []
        return [track for entry in entries if (track := _to_track(entry)) is not None]

    @asynccontextmanager
    async def download(self, track: Track) -> AsyncIterator[DownloadedAudio]:
        """Download ``track`` as MP3; the file is deleted when the ``async with`` exits.

        Raises:
            TooLongError: If ``track.duration`` is over ``MAX_DURATION``.
            TooLargeError: If the MP3 is over ``UPLOAD_LIMIT_BYTES``.
            PreviewOnlyError: If SoundCloud serves only a preview or a DRM-locked stream.
            ProviderError: If yt-dlp fails or the download takes longer than the timeout.
        """
        if track.duration > MAX_DURATION:
            raise TooLongError(f"Track lasts {track.duration} s, the limit is {MAX_DURATION} s")

        directory = Path(tempfile.mkdtemp(prefix="xemo-"))
        try:
            info = await self._run_download(track.page_url, directory)
            yield _to_audio(info, track)
        finally:
            # A single small file: quick enough to do inline, and it keeps the cleanup
            # from being skipped when the task is cancelled while we await.
            shutil.rmtree(directory, ignore_errors=True)

    async def _run_download(self, url: str, directory: Path) -> Mapping[str, Any]:
        """Run the downloader in a thread under a download slot and the timeout.

        The timeout bounds how long the download may run before the worker is told to
        stop, not how long this call takes: yt-dlp only checks the stop flag between
        chunks, fragments and post-processing steps, so the worker can still spend up to
        ``socket_timeout`` per retry on a request in flight, or finish an ffmpeg run
        (seconds). The call returns, and the slot and directory are released, only once
        the thread has really ended.
        """
        loop = asyncio.get_running_loop()
        cancel = threading.Event()
        # Set from the thread itself, so "finished" cannot be faked by a cancelled task.
        finished: asyncio.Future[None] = loop.create_future()

        def work() -> Mapping[str, Any]:
            try:
                return self._download(url, directory, cancel)
            except YoutubeDLError as exc:
                # yt-dlp has no error type for locked tracks, only this message.
                if "DRM protected" in str(exc):
                    raise PreviewOnlyError("SoundCloud serves this track only as DRM") from exc
                raise ProviderError(f"SoundCloud download failed: {exc}") from exc
            except OSError as exc:  # disk full, ffmpeg could not start, socket errors
                raise ProviderError(f"SoundCloud download failed: {exc}") from exc
            finally:
                # The loop is already closed if it shut down while we ran.
                with contextlib.suppress(RuntimeError):
                    loop.call_soon_threadsafe(_set_done, finished)

        async with self._download_slots:
            outcome = loop.run_in_executor(None, work)
            try:
                # Shielded: a timeout must not abandon the thread; we wait for it below.
                return await asyncio.wait_for(asyncio.shield(outcome), self._download_timeout)
            except TimeoutError as exc:
                # Errors from the thread arrive as ProviderError, so this is the timeout.
                raise ProviderError(
                    f"SoundCloud download took longer than {self._download_timeout:g} s"
                ) from exc
            finally:
                cancel.set()
                await _wait_uncancellable(finished)
                if outcome.done() and not outcome.cancelled():
                    outcome.exception()  # mark retrieved; its outcome no longer matters


def _set_done(future: asyncio.Future[None]) -> None:
    """Resolve ``future`` unless the waiter has already given up on it."""
    if not future.done():
        future.set_result(None)


async def _wait_uncancellable(future: asyncio.Future[None]) -> None:
    """Wait for ``future`` even if the current task is cancelled, then re-raise that.

    A worker thread cannot be killed, so releasing its slot and directory early (on a
    second cancel, or on loop shutdown) would let it write into a deleted directory.
    """
    cancelled = False
    while not future.done():
        try:
            await asyncio.shield(future)
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError


def _to_audio(info: Mapping[str, Any], track: Track) -> DownloadedAudio:
    """Check a finished download and describe its MP3 file.

    Raises:
        PreviewOnlyError: If the chosen format is SoundCloud's 30 s preview of the track.
        ProviderError: If yt-dlp reported no output file.
        TooLargeError: If the file is over the upload limit.
    """
    # yt-dlp marks previews in the format id, e.g. ``http_mp3_1_0_preview``.
    if str(info.get("format_id") or "").endswith("preview"):
        raise PreviewOnlyError("SoundCloud serves only a preview of this track")

    downloads = info.get("requested_downloads") or [{}]
    filepath = downloads[0].get("filepath")
    path = Path(filepath) if isinstance(filepath, str) else None
    if path is None or not path.is_file():
        raise ProviderError("yt-dlp finished without an audio file")

    size = path.stat().st_size
    if size > UPLOAD_LIMIT_BYTES:
        raise TooLargeError(f"MP3 is {size} bytes, the limit is {UPLOAD_LIMIT_BYTES}")
    duration = info.get("duration")
    return DownloadedAudio(
        path=path,
        duration=round(duration) if isinstance(duration, int | float) else track.duration,
        size=size,
    )


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
