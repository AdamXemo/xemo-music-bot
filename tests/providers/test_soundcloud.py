import asyncio
import threading
import time
from collections.abc import Mapping
from typing import Any

import pytest
from yt_dlp.utils import DownloadError

from xemo_music_bot.core.models import Track
from xemo_music_bot.providers.base import ProviderError
from xemo_music_bot.providers.soundcloud import SoundCloudProvider

ARTWORK = "https://i1.sndcdn.com/artworks-000048087574-7vki2d"

# Trimmed from a real `scsearch` entry (yt-dlp 2026.8.19, extract_flat="in_playlist").
ENTRY: dict[str, Any] = {
    "_type": "url",
    "ie_key": "Soundcloud",
    "url": "https://api.soundcloud.com/tracks/soundcloud%3Atracks%3A92297366",
    "id": "92297366",
    "title": "Daft Punk - Instant Crush (Official Audio)",
    "uploader": "Aaron Gardea",
    "duration": 300.525,
    "webpage_url": "https://soundcloud.com/aaron-gardea/daft-punk-instant-crush",
    "thumbnails": [
        {"id": "large", "url": f"{ARTWORK}-large.jpg", "width": 100, "height": 100},
        {"id": "t500x500", "url": f"{ARTWORK}-t500x500.jpg", "width": 500, "height": 500},
        {"id": "original", "url": f"{ARTWORK}-original.jpg", "preference": 10},
    ],
    "formats": None,
}


class FakeExtractor:
    """Stands in for yt-dlp: records search keys and returns canned entries."""

    def __init__(self, *entries: Mapping[str, Any], error: Exception | None = None) -> None:
        self.entries = list(entries)
        self.error = error
        self.calls: list[str] = []

    def __call__(self, url: str) -> Mapping[str, Any]:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        return {"_type": "playlist", "id": url, "entries": self.entries}


async def test_search_turns_yt_dlp_entry_into_clean_track() -> None:
    extractor = FakeExtractor(ENTRY)

    tracks = await SoundCloudProvider(extractor).search("  instant   crush ", limit=5)

    assert extractor.calls == ["scsearch5:instant crush"]
    assert tracks == [
        Track(
            provider="soundcloud",
            provider_track_id="92297366",
            title="Instant Crush",
            artist="Daft Punk",
            duration=301,
            artwork_url=f"{ARTWORK}-t500x500.jpg",
            page_url="https://soundcloud.com/aaron-gardea/daft-punk-instant-crush",
        )
    ]


@pytest.mark.parametrize(
    ("thumbnails", "expected"),
    [
        pytest.param(
            [{"url": "https://a1.sndcdn.com/images/default_avatar.png"}],
            "https://a1.sndcdn.com/images/default_avatar.png",
            id="single unsized url is used",
        ),
        pytest.param(None, None, id="no thumbnails gives no artwork"),
    ],
)
async def test_search_artwork_fallback(
    thumbnails: list[dict[str, str]] | None, expected: str | None
) -> None:
    extractor = FakeExtractor({**ENTRY, "thumbnails": thumbnails})

    [track] = await SoundCloudProvider(extractor).search("instant crush", limit=1)

    assert track.artwork_url == expected


@pytest.mark.parametrize(
    "missing", ["id", "title", "duration", "webpage_url"], ids=lambda field: f"without {field}"
)
async def test_search_skips_entries_without_required_fields(missing: str) -> None:
    broken = {key: value for key, value in ENTRY.items() if key != missing}
    extractor = FakeExtractor(broken, {**ENTRY, "id": "2"})

    tracks = await SoundCloudProvider(extractor).search("instant crush", limit=5)

    assert [track.provider_track_id for track in tracks] == ["2"]


async def test_search_leaves_artist_empty_without_uploader() -> None:
    extractor = FakeExtractor({**ENTRY, "title": "Instant Crush", "uploader": None})

    [track] = await SoundCloudProvider(extractor).search("instant crush", limit=1)

    assert (track.artist, track.title) == ("", "Instant Crush")


async def test_search_returns_empty_list_when_nothing_found() -> None:
    tracks = await SoundCloudProvider(FakeExtractor()).search("zzzz", limit=5)

    assert tracks == []


async def test_search_does_not_call_yt_dlp_for_blank_query() -> None:
    extractor = FakeExtractor(ENTRY)

    tracks = await SoundCloudProvider(extractor).search(" \n ", limit=5)

    assert tracks == []
    assert extractor.calls == []


async def test_search_rejects_limit_below_one() -> None:
    with pytest.raises(ValueError, match="limit"):
        await SoundCloudProvider(FakeExtractor()).search("instant crush", limit=0)


async def test_search_raises_provider_error_when_yt_dlp_fails() -> None:
    extractor = FakeExtractor(error=DownloadError("Unable to download API page"))

    with pytest.raises(ProviderError, match="Unable to download API page"):
        await SoundCloudProvider(extractor).search("instant crush", limit=5)


async def test_search_runs_at_most_max_concurrency_yt_dlp_calls() -> None:
    running = 0
    peak = 0
    lock = threading.Lock()

    def slow_extractor(url: str) -> Mapping[str, Any]:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.05)  # yt-dlp blocks its worker thread like this
        with lock:
            running -= 1
        return {"entries": []}

    provider = SoundCloudProvider(slow_extractor, max_concurrency=2)

    await asyncio.gather(*(provider.search(f"query {n}", limit=1) for n in range(5)))

    assert peak == 2
