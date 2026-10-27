from dataclasses import replace

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from xemo_music_bot.core.models import Track
from xemo_music_bot.db.models import CachedTrack
from xemo_music_bot.db.repositories.tracks import TracksRepository

TRACK = Track("soundcloud", "42", "Song", "Artist", 181, None, "https://sc/42")


@pytest.fixture
def factory(connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    # Commits become savepoints, so the connection fixture still rolls everything back.
    return async_sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )


@pytest.fixture
def tracks(factory: async_sessionmaker[AsyncSession]) -> TracksRepository:
    return TracksRepository(factory)


async def rows(factory: async_sessionmaker[AsyncSession]) -> list[tuple[object, ...]]:
    statement = select(
        CachedTrack.provider,
        CachedTrack.provider_track_id,
        CachedTrack.title,
        CachedTrack.artist,
        CachedTrack.duration,
        CachedTrack.tg_file_id,
    ).order_by(CachedTrack.provider)
    async with factory() as session:
        return [tuple(row) for row in await session.execute(statement)]


async def test_save_stores_the_file_id_and_a_later_save_overwrites_it(
    tracks: TracksRepository, factory: async_sessionmaker[AsyncSession]
) -> None:
    assert await tracks.get_file_id(TRACK) is None

    await tracks.save(TRACK, "stale")
    assert await tracks.get_file_id(TRACK) == "stale"
    assert await rows(factory) == [("soundcloud", "42", "Song", "Artist", 181, "stale")]

    # The unique pair conflicts, so the row is updated in place, not duplicated.
    await tracks.save(replace(TRACK, title="Song (Edit)", duration=180), "fresh")
    assert await rows(factory) == [("soundcloud", "42", "Song (Edit)", "Artist", 180, "fresh")]
    # The same id from another provider is another track.
    assert await tracks.get_file_id(replace(TRACK, provider="youtube")) is None


async def test_delete_stale_removes_the_row_holding_that_file_id(
    tracks: TracksRepository,
) -> None:
    await tracks.save(TRACK, "stale")

    await tracks.delete_stale(TRACK, "stale")

    assert await tracks.get_file_id(TRACK) is None


async def test_delete_stale_keeps_a_file_id_saved_since(tracks: TracksRepository) -> None:
    # Another user's download replaced the stale id before this delete ran.
    await tracks.save(TRACK, "fresh")

    await tracks.delete_stale(TRACK, "stale")

    assert await tracks.get_file_id(TRACK) == "fresh"


@pytest.mark.parametrize(
    "track",
    [
        pytest.param(replace(TRACK, title=""), id="empty-title"),
        pytest.param(replace(TRACK, duration=-1), id="negative-duration"),
    ],
)
async def test_save_refuses_rows_the_checks_forbid(tracks: TracksRepository, track: Track) -> None:
    with pytest.raises(IntegrityError):
        await tracks.save(track, "id")
