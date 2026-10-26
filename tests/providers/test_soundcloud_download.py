import asyncio
import logging
import threading
from collections.abc import Iterator, Mapping
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, ClassVar

import pytest
from PIL import Image
from rich.console import Console
from yt_dlp.utils import DownloadCancelled, DownloadError

from xemo_music_bot import timing
from xemo_music_bot.core.models import Track
from xemo_music_bot.providers import soundcloud
from xemo_music_bot.providers.base import (
    PreviewOnlyError,
    ProviderError,
    TooLargeError,
    TooLongError,
)
from xemo_music_bot.providers.covers import DEFAULT_COVER
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
        cover: bytes | None = None,
    ) -> None:
        self.content = content
        self.info = {"format_id": "hls_aac_160k", "duration": 299.6, **(info or {})}
        self.error = error
        self.writes_file = writes_file
        self.cover = cover
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
        thumbnails = [{"id": "t300x300", "url": "https://i1.sndcdn.com/a-t300x300.jpg"}]
        if self.cover is not None:
            # yt-dlp's writethumbnail records the saved file on the thumbnail it fetched.
            cover = directory / "92297366.jpg"
            cover.write_bytes(self.cover)
            thumbnails.append({"id": "t500x500", "filepath": str(cover)})
        path = directory / "92297366.mp3"
        path.write_bytes(self.content)
        return {
            **self.info,
            "thumbnails": thumbnails,
            "requested_downloads": [{"filepath": str(path)}],
        }


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


def jpeg(width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "blue").save(buffer, "JPEG")
    return buffer.getvalue()


async def test_download_yields_a_thumbnail_of_the_cover_and_removes_it_afterwards() -> None:
    downloader = FakeDownloader(cover=jpeg(500, 500))

    async with SoundCloudProvider(downloader=downloader).download(TRACK) as audio:
        assert audio.thumbnail.parent == downloader.directory
        with Image.open(audio.thumbnail) as thumbnail:
            assert (thumbnail.format, thumbnail.size) == ("JPEG", (320, 320))

    assert not audio.thumbnail.exists()


async def test_download_uses_the_default_cover_when_yt_dlp_saved_none() -> None:
    async with SoundCloudProvider(downloader=FakeDownloader()).download(TRACK) as audio:
        assert audio.thumbnail == DEFAULT_COVER

    assert DEFAULT_COVER.is_file()  # the cleanup must never touch the bundled file


async def test_download_uses_the_default_cover_when_the_cover_is_broken() -> None:
    downloader = FakeDownloader(cover=b"<html>Forbidden</html>")

    async with SoundCloudProvider(downloader=downloader).download(TRACK) as audio:
        assert audio.thumbnail == DEFAULT_COVER
        assert audio.path.is_file()


@pytest.mark.parametrize(
    ("widths", "kept"),
    [
        pytest.param([16, 300, 400, 500, None], [16, 300, 400, 500], id="drops-original"),
        pytest.param([None], [None], id="keeps-unknown-sizes-when-nothing-else"),
        pytest.param([640, 1280], [640, 1280], id="keeps-all-when-none-is-small-enough"),
    ],
)
def test_cover_sizes_skip_covers_over_500_px(
    widths: list[int | None], kept: list[int | None]
) -> None:
    thumbnails = [{"url": f"https://i1.sndcdn.com/{w}.jpg", "width": w} for w in widths]

    narrowed = soundcloud._cover_sizes(thumbnails)

    assert [thumb["width"] for thumb in narrowed or []] == kept


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


class RecordingYoutubeDL:
    """Stands in for yt_dlp.YoutubeDL and records how the downloader drives it."""

    calls: ClassVar[list[tuple[str, Any, dict[str, Any]]]] = []
    options: ClassVar[dict[str, Any]] = {}

    def __init__(self, options: dict[str, Any]) -> None:
        RecordingYoutubeDL.options = options

    def __enter__(self) -> "RecordingYoutubeDL":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def extract_info(self, url: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("extract_info", url, kwargs))
        return {
            "id": "1",
            "thumbnails": [{"id": "t500x500", "width": 500}, {"id": "original"}],
        }

    def process_ie_result(self, info: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("process_ie_result", info, kwargs))
        return {"id": "1", "processed": True}


@pytest.fixture
def plain_timings(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    """Log every timing stage as a plain line during the test, then turn timings off."""
    caplog.set_level(logging.INFO, logger="xemo_music_bot.timing")
    timing.configure("stages", Console(file=StringIO(), force_terminal=False))
    yield
    timing.configure("off")


@pytest.mark.usefixtures("plain_timings")
async def test_download_stages_include_those_reported_from_the_worker_thread(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def downloader(url: str, directory: Path, cancel: threading.Event) -> Mapping[str, Any]:
        # Like a yt-dlp hook: only sees the tap's task if the context reached the thread.
        timing.begin("fetch audio", detail="stage")
        timing.end("fetch audio")
        return FakeDownloader()(url, directory, cancel)

    with timing.timed_task("tap"):
        async with SoundCloudProvider(downloader=downloader).download(TRACK):
            pass

    assert [m for m in caplog.messages if m.startswith("▶")] == [
        "▶ tap",
        "▶ tap: download",
        "▶ tap: wait for download slot",
        "▶ tap: fetch audio",
        "▶ tap: thumbnail",
    ]


def yt_dlp_hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The hook download_with_yt_dlp gives yt-dlp, from a run against a fake YoutubeDL."""
    monkeypatch.setattr(soundcloud, "YoutubeDL", RecordingYoutubeDL)
    soundcloud.download_with_yt_dlp("https://sc/1", tmp_path, threading.Event())
    [hook] = RecordingYoutubeDL.options["progress_hooks"]
    return hook


@pytest.mark.usefixtures("plain_timings")
def test_download_hooks_ignore_reports_timings_cannot_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    hook = yt_dlp_hook(tmp_path, monkeypatch)

    def broken(_progress: Mapping[str, Any]) -> None:
        raise TypeError("unsupported operand type(s) for //: 'int' and 'NoneType'")

    monkeypatch.setattr(soundcloud, "_report_stage", broken)

    with timing.timed_task("tap"):
        hook({"status": "downloading", "total_bytes": None})  # must not fail the download

    assert "Timing hook failed" in [r.getMessage() for r in caplog.records]


def test_download_hooks_skip_timing_reports_when_no_task_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = yt_dlp_hook(tmp_path, monkeypatch)
    reports: list[Mapping[str, Any]] = []
    monkeypatch.setattr(soundcloud, "_report_stage", reports.append)

    hook({"status": "downloading"})

    assert reports == []


@pytest.mark.usefixtures("plain_timings")
def test_download_reports_become_stages_and_unknown_ones_are_ignored(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reports: list[dict[str, Any]] = [
        {"status": "downloading", "fragment_index": 1, "fragment_count": 9},
        {"status": "downloading", "fragment_index": 2, "fragment_count": 9},
        {"status": "error"},
        {"status": "finished"},
        {"status": "started", "postprocessor": "FixupM3u8"},
        {"status": "started", "postprocessor": "ExtractAudio"},
        {"status": "processing", "postprocessor": "ExtractAudio"},
        {"status": "finished", "postprocessor": "ExtractAudio"},
        {"status": "started", "postprocessor": "MoveFilesAfterDownload"},
    ]

    with timing.timed_task("tap"):
        timing.begin("prepare", detail="stage")
        for report in reports:
            soundcloud._report_stage(report)

    steps = [m.split(" finished")[0] for m in caplog.messages if m.startswith(("▶ tap:", "✓"))]
    assert steps == [
        "▶ tap: prepare",
        "✓ tap: prepare",
        "▶ tap: fetch audio",
        "✓ tap: fetch audio",
        "▶ tap: convert to MP3",
        "✓ tap: convert to MP3",
        "✓ tap",
    ]


@pytest.mark.parametrize(
    ("progress", "text"),
    [
        pytest.param({"fragment_index": 3, "fragment_count": 40}, "3/40 fragments", id="hls"),
        pytest.param({"downloaded_bytes": 410, "total_bytes": 1000}, "41%", id="bytes"),
        pytest.param(
            {"downloaded_bytes": 500, "total_bytes": None, "total_bytes_estimate": 2000},
            "25%",
            id="estimate-only",
        ),
        pytest.param(
            {"downloaded_bytes": 2500, "total_bytes_estimate": 2000}, "100%", id="low-estimate"
        ),
        pytest.param({"fragment_count": 9}, None, id="fragment-index-unknown"),
        pytest.param({"downloaded_bytes": 500, "total_bytes": None}, None, id="no-total"),
        pytest.param({}, None, id="nothing-known"),
    ],
)
def test_download_progress_text(progress: dict[str, Any], text: str | None) -> None:
    assert soundcloud._progress_text(progress) == text


@pytest.mark.parametrize("hooks", ["progress_hooks", "postprocessor_hooks"])
def test_download_hooks_still_stop_a_cancelled_download(
    hooks: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(soundcloud, "YoutubeDL", RecordingYoutubeDL)
    cancel = threading.Event()
    cancel.set()
    soundcloud.download_with_yt_dlp("https://sc/1", tmp_path, cancel)
    [hook] = RecordingYoutubeDL.options[hooks]

    with pytest.raises(DownloadCancelled):
        hook({"status": "downloading"})


@pytest.mark.usefixtures("plain_timings")
def test_download_times_the_resolve_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(soundcloud, "YoutubeDL", RecordingYoutubeDL)

    with timing.timed_task("tap"):
        soundcloud.download_with_yt_dlp("https://sc/1", tmp_path, threading.Event())

    assert "▶ tap: resolve" in caplog.messages
    assert any(m.startswith("✓ tap: resolve finished in") for m in caplog.messages)


def test_download_asks_yt_dlp_for_the_cover_without_the_original_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    RecordingYoutubeDL.calls = []
    monkeypatch.setattr(soundcloud, "YoutubeDL", RecordingYoutubeDL)

    info = soundcloud.download_with_yt_dlp("https://sc/1", tmp_path, threading.Event())

    (_, url, extract_kwargs), (_, found, process_kwargs) = RecordingYoutubeDL.calls
    assert url == "https://sc/1"
    assert extract_kwargs == {"download": False, "process": False}
    assert process_kwargs == {"download": True}
    assert [size["id"] for size in found["thumbnails"]] == ["t500x500"]
    assert RecordingYoutubeDL.options["writethumbnail"] is True
    assert info == {"id": "1", "processed": True}
