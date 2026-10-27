"""Reads and writes the ``tracks`` table: Telegram ``file_id``s of tracks already sent."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from xemo_music_bot.core.models import Track
from xemo_music_bot.db.models import CachedTrack


class TracksRepository:
    """The ``file_id`` cache, one short committed transaction per call.

    The exception to "repositories never commit" (why: ARCHITECTURE, Data model). Each
    call opens its own session from the factory, so it takes a second pool connection
    while the update's session holds one.

    Args:
        session_factory: The application's long-lived session factory.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_file_id(self, track: Track) -> str | None:
        """Return the stored ``file_id`` of the track, or ``None`` if it was never sent."""
        statement = select(CachedTrack.tg_file_id).where(
            CachedTrack.provider == track.provider,
            CachedTrack.provider_track_id == track.provider_track_id,
        )
        async with self._session_factory.begin() as session:
            return await session.scalar(statement)

    async def save(self, track: Track, file_id: str) -> None:
        """Store the track's ``file_id`` with its cleaned metadata; the last save wins.

        A row left by an earlier send is overwritten, so a track downloaded again after a
        stale ``file_id`` keeps the new one.
        """
        values = {
            "title": track.title,
            "artist": track.artist,
            "duration": track.duration,
            "tg_file_id": file_id,
        }
        statement = (
            insert(CachedTrack)
            .values(provider=track.provider, provider_track_id=track.provider_track_id, **values)
            .on_conflict_do_update(constraint="uq_tracks_provider_provider_track_id", set_=values)
        )
        async with self._session_factory.begin() as session:
            await session.execute(statement)

    async def delete_stale(self, track: Track, file_id: str) -> None:
        """Delete the track's row if it still holds ``file_id``, which Telegram rejected.

        Compare-and-delete: another user may have stored a fresh ``file_id`` since this
        one was read, and that one must survive.
        """
        statement = delete(CachedTrack).where(
            CachedTrack.provider == track.provider,
            CachedTrack.provider_track_id == track.provider_track_id,
            CachedTrack.tg_file_id == file_id,
        )
        async with self._session_factory.begin() as session:
            await session.execute(statement)
