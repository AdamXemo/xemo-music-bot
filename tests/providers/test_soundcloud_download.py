import asyncio
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from yt_dlp.utils import DownloadError

from xemo_music_bot.core.models import Track
from xemo_music_bot.providers import soundcloud
from xemo_music_bot.providers.base import (
    PreviewOnlyError,
    ProviderError,
    TooLargeError,
    TooLongError,
)
from xemo_music_bot.providers.soundcloud import MAX_DURATION, SoundCloudProvider

TRACK = Track(
    provider="soundcloud",
    provider_track_id="92297366",
    title="Instant Crush",
    artist="Daft Punk",
    duration=300,
    artwork_url=None,
    page_url="https://soundcloud.com/aaron-gardea/daft-punk-instant-crush",
)


class FakeDownloader:
    """Stands in for yt-dlp: writes a fake MP3 and returns an info dict like yt-dlp's."""

    def __init__(
        self,
        *,
        content: bytes = b"ID3" + bytes(1000),
        info: Mapping[str, Any] | None = None,
        error: Exception | None = None,
        writes_file: bool = True,
    ) -> None:
        self.content = content
        self.info = {"format_id": "hls_aac_160k", "duration": 299.6, **(info or {})}
        self.error = error
        self.writes_file = writes_file
        self.calls: list[tuple[str, Path]] = []

    @property
    def directory(self) -> Path:
        return self.calls[-1][1]

    def __call__(self, url: str, directory: Path, cancel: threading.Event) -> Mapping[str, Any]:
        self.calls.append((url, directory))
        if self.error is not None:
            raise self.error
        if not self.writes_file:
            return self.info
        path = directory / "92297366.mp3"
        path.write_bytes(self.content)
        return {**self.info, "requested_downloads": [{"filepath": str(path)}]}


async def test_download_yields_mp3_and_removes_its_directory_afterwards() -> None:
    downloader = FakeDownloader()

    async with SoundCloudProvider(downloader=downloader).download(TRACK) as audio:
        assert downloader.calls == [(TRACK.page_url, downloader.directory)]
        assert audio.path.read_bytes() == downloader.content
        assert audio.path.suffix == ".mp3"
        assert audio.size == len(downloader.content)
        assert audio.duration == 300  # yt-dlp's 299.6 rounded

    assert not downloader.directory.exists()


async def test_download_removes_directory_when_the_upload_fails() -> None:
    downloader = FakeDownloader()

    with pytest.raises(RuntimeError, match="upload failed"):
        async with SoundCloudProvider(downloader=downloader).download(TRACK):
            raise RuntimeError("upload failed")

    assert not downloader.directory.exists()


async def test_download_uses_track_duration_when_yt_dlp_reports_none() -> None:
    downloader = FakeDownloader(info={"duration": None})

    async with SoundCloudProvider(downloader=downloader).download(TRACK) as audio:
        assert audio.duration == TRACK.duration


async def test_download_refuses_a_track_too_long_before_downloading() -> None:
    downloader = FakeDownloader()
    long_track = Track("soundcloud", "1", "Mix", "DJ", MAX_DURATION + 1, None, "https://sc/1")

    with pytest.raises(TooLongError):
        async with SoundCloudProvider(downloader=downloader).download(long_track):
            pytest.fail("the body must not run")

    assert downloader.calls == []


async def test_download_accepts_a_track_at_the_duration_limit() -> None:
    track = Track("soundcloud", "1", "Mix", "DJ", MAX_DURATION, None, "https://sc/1")

    async with SoundCloudProvider(downloader=FakeDownloader()).download(track) as audio:
        assert audio.path.is_file()


async def test_download_rejects_a_file_over_the_upload_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(soundcloud, "UPLOAD_LIMIT_BYTES", 10)
    downloader = FakeDownloader(content=bytes(11))

    with pytest.raises(TooLargeError):
        async with SoundCloudProvider(downloader=downloader).download(TRACK):
            pytest.fail("the body must not run")

    assert not downloader.directory.exists()


async def test_download_accepts_a_file_at_the_upload_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(soundcloud, "UPLOAD_LIMIT_BYTES", 10)

    async with SoundCloudProvider(downloader=FakeDownloader(content=bytes(10))).download(
        TRACK
    ) as audio:
        assert audio.size == 10


async def test_download_rejects_a_preview_and_removes_it() -> None:
    # Go+ tracks: the only format is a 30 s preview, named so by yt-dlp.
    downloader = FakeDownloader(info={"format_id": "http_mp3_1_0_preview", "duration": 30.0})

    with pytest.raises(PreviewOnlyError):
        async with SoundCloudProvider(downloader=downloader).download(TRACK):
            pytest.fail("the body must not run")

    assert not downloader.directory.exists()


async def test_download_reports_drm_locked_track_as_preview_only() -> None:
    downloader = FakeDownloader(error=DownloadError("[soundcloud] 7: This video is DRM protected"))

    with pytest.raises(PreviewOnlyError):
        async with SoundCloudProvider(downloader=downloader).download(TRACK):
            pytest.fail("the body must not run")

    assert not downloader.directory.exists()


async def test_download_raises_provider_error_when_yt_dlp_fails() -> None:
    downloader = FakeDownloader(error=DownloadError("Unable to download API page"))

    with pytest.raises(ProviderError, match="Unable to download API page") as excinfo:
        async with SoundCloudProvider(downloader=downloader).download(TRACK):
            pytest.fail("the body must not run")

    assert type(excinfo.value) is ProviderError
    assert not downloader.directory.exists()


async def test_download_raises_provider_error_when_no_file_was_written() -> None:
    downloader = FakeDownloader(writes_file=False)

    with pytest.raises(ProviderError, match="without an audio file"):
        async with SoundCloudProvider(downloader=downloader).download(TRACK):
            pytest.fail("the body must not run")

    assert not downloader.directory.exists()


async def test_download_times_out_and_stops_the_worker_before_cleaning_up() -> None:
    stopped = threading.Event()
    directories: list[Path] = []

    def slow_downloader(url: str, directory: Path, cancel: threading.Event) -> Mapping[str, Any]:
        directories.append(directory)
        # A real download notices the flag in a yt-dlp progress hook.
        assert cancel.wait(timeout=5), "the provider never asked the worker to stop"
        stopped.set()
        raise DownloadError("The download was cancelled")

    provider = SoundCloudProvider(downloader=slow_downloader, download_timeout=0.05)

    with pytest.raises(ProviderError, match="took longer"):
        async with provider.download(TRACK):
            pytest.fail("the body must not run")

    assert stopped.is_set()  # the provider waited for the thread, it did not abandon it
    assert not directories[0].exists()


async def test_download_raises_provider_error_when_the_disk_or_ffmpeg_fails() -> None:
    downloader = FakeDownloader(error=OSError("No space left on device"))

    with pytest.raises(ProviderError, match="No space left") as excinfo:
        async with SoundCloudProvider(downloader=downloader).download(TRACK):
            pytest.fail("the body must not run")

    assert type(excinfo.value) is ProviderError
    assert not downloader.directory.exists()


async def test_download_does_not_mistake_a_socket_timeout_for_its_own_timeout() -> None:
    downloader = FakeDownloader(error=TimeoutError("read timed out"))

    with pytest.raises(ProviderError, match="read timed out"):
        async with SoundCloudProvider(downloader=downloader).download(TRACK):
            pytest.fail("the body must not run")


class StuckDownloader:
    """Blocks in a worker thread until released, or until asked to stop if it can be."""

    def __init__(self, *, stops_when_asked: bool = False) -> None:
        self.stops_when_asked = stops_when_asked
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.directories: list[Path] = []

    def __call__(self, url: str, directory: Path, cancel: threading.Event) -> Mapping[str, Any]:
        self.directories.append(directory)
        self.started.set()
        # A request in flight cannot react to the flag; a progress hook can.
        (cancel if self.stops_when_asked else self.release).wait(timeout=5)
        self.finished.set()
        raise DownloadError("The download was cancelled")


async def fetch(provider: SoundCloudProvider) -> None:
    async with provider.download(TRACK):
        pytest.fail("the body must not run")


async def test_download_cancelled_by_caller_stops_the_worker_and_removes_the_dir() -> None:
    downloader = StuckDownloader(stops_when_asked=True)
    task = asyncio.create_task(fetch(SoundCloudProvider(downloader=downloader)))
    await asyncio.to_thread(downloader.started.wait, 5)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert downloader.finished.is_set()
    assert not downloader.directories[0].exists()


async def test_download_cancelled_twice_still_waits_for_the_worker() -> None:
    downloader = StuckDownloader()
    provider = SoundCloudProvider(downloader=downloader, max_downloads=1)
    task = asyncio.create_task(fetch(provider))
    await asyncio.to_thread(downloader.started.wait, 5)

    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()  # for example the event loop shutting down
    await asyncio.sleep(0.05)
    waiting = asyncio.create_task(fetch(provider))
    await asyncio.sleep(0.05)

    assert not task.done()
    assert downloader.directories[0].exists()  # the thread may still write into it
    assert len(downloader.directories) == 1  # and still holds the only download slot

    downloader.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert downloader.finished.is_set()
    assert not downloader.directories[0].exists()
    with pytest.raises(ProviderError):
        await waiting  # got the slot only after the first worker ended


async def test_download_runs_at_most_max_downloads_yt_dlp_calls() -> None:
    running = 0
    peak = 0
    lock = threading.Lock()
    # Two threads must be inside at once to pass, so a cap of 1 would time out.
    pair = threading.Barrier(2, timeout=5)

    def downloader(url: str, directory: Path, cancel: threading.Event) -> Mapping[str, Any]:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        pair.wait()
        with lock:
            running -= 1
        path = directory / "a.mp3"
        path.write_bytes(b"ID3")
        return {"requested_downloads": [{"filepath": str(path)}]}

    provider = SoundCloudProvider(downloader=downloader, max_downloads=2)

    async def get_audio() -> None:
        async with provider.download(TRACK):
            pass

    await asyncio.gather(*(get_audio() for _ in range(4)))

    assert peak == 2
