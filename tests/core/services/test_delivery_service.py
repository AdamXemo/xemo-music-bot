import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from xemo_music_bot.core.models import DownloadedAudio, Track
from xemo_music_bot.core.services.delivery import DeliveryService, StaleFileIdError
from xemo_music_bot.db.repositories.tracks import TracksRepository

TRACK = Track("soundcloud", "42", "Song", "Artist", 181, None, "https://sc/42")
AUDIO = DownloadedAudio(path=Path("song.mp3"), duration=181, size=3, thumbnail=Path("c.jpg"))


class FakeTracks(TracksRepository):
    """The file_id cache in a dict; ``save_error`` makes every save fail."""

    def __init__(self) -> None:
        self.file_ids: dict[Track, str] = {}
        self.save_error: Exception | None = None
        self.deleted: list[tuple[Track, str]] = []

    async def get_file_id(self, track: Track) -> str | None:
        return self.file_ids.get(track)

    async def save(self, track: Track, file_id: str) -> None:
        if self.save_error is not None:
            raise self.save_error
        self.file_ids[track] = file_id

    async def delete_stale(self, track: Track, file_id: str) -> None:
        self.deleted.append((track, file_id))
        self.file_ids.pop(track, None)


class FakeProvider:
    """Yields canned audio and records which tracks it downloaded."""

    def __init__(self) -> None:
        self.downloaded: list[Track] = []

    async def search(self, query: str, limit: int) -> list[Track]:
        raise AssertionError("Delivery must not search")

    @asynccontextmanager
    async def download(self, track: Track) -> AsyncIterator[DownloadedAudio]:
        self.downloaded.append(track)
        yield AUDIO


class Sender:
    """Records what was sent; ``error`` makes the send fail, ``file_id`` is its result."""

    def __init__(self, error: Exception | None = None, file_id: str | None = "new") -> None:
        self.error = error
        self.file_id = file_id
        self.sent: list[object] = []

    async def by_id(self, file_id: str) -> None:
        self.sent.append(file_id)
        if self.error is not None:
            raise self.error

    async def upload(self, audio: DownloadedAudio) -> str | None:
        self.sent.append(audio)
        if self.error is not None:
            raise self.error
        return self.file_id


@pytest.fixture
def tracks() -> FakeTracks:
    return FakeTracks()


@pytest.fixture
def service(tracks: FakeTracks) -> DeliveryService:
    return DeliveryService(FakeProvider(), tracks, max_duration=1000)


async def test_send_cached_sends_the_stored_file_id(
    service: DeliveryService, tracks: FakeTracks
) -> None:
    tracks.file_ids[TRACK] = "cached"
    sender = Sender()

    assert await service.send_cached(TRACK, sender.by_id) is True
    assert sender.sent == ["cached"]


async def test_a_rejected_file_id_is_forgotten_so_the_track_downloads_again(
    service: DeliveryService, tracks: FakeTracks
) -> None:
    tracks.file_ids[TRACK] = "stale"

    assert await service.send_cached(TRACK, Sender(StaleFileIdError()).by_id) is False
    # The id that failed is passed on, so the delete spares a fresher one.
    assert tracks.deleted == [(TRACK, "stale")]


async def test_any_other_send_error_propagates_and_keeps_the_file_id(
    service: DeliveryService, tracks: FakeTracks
) -> None:
    tracks.file_ids[TRACK] = "cached"

    with pytest.raises(ConnectionError):
        await service.send_cached(TRACK, Sender(ConnectionError()).by_id)
    assert tracks.deleted == []


async def test_deliver_stores_the_file_id_of_the_upload(
    service: DeliveryService, tracks: FakeTracks
) -> None:
    sender = Sender(file_id="new")

    await service.deliver(TRACK, sender.upload)

    assert sender.sent == [AUDIO]
    assert tracks.file_ids == {TRACK: "new"}


async def test_deliver_stores_nothing_when_the_send_fails(
    service: DeliveryService, tracks: FakeTracks
) -> None:
    with pytest.raises(ConnectionError):
        await service.deliver(TRACK, Sender(ConnectionError()).upload)

    assert tracks.file_ids == {}


async def test_deliver_stores_nothing_when_telegram_returns_no_file_id(
    service: DeliveryService, tracks: FakeTracks
) -> None:
    await service.deliver(TRACK, Sender(file_id=None).upload)

    assert tracks.file_ids == {}


async def test_a_failed_save_is_logged_but_not_raised(
    service: DeliveryService, tracks: FakeTracks, caplog: pytest.LogCaptureFixture
) -> None:
    tracks.save_error = OSError("database down")

    await service.deliver(TRACK, Sender().upload)

    assert "Could not cache the file_id of https://sc/42" in caplog.messages
    assert caplog.records[-1].levelno == logging.WARNING
