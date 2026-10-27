"""Reads and writes rows of the ``invites`` table."""

from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.db.models import Invite


class InvitesRepository:
    """Queries for :class:`Invite` within the caller's session.

    It never commits: whoever opened the session owns the transaction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, code: str, created_by: int, ttl: timedelta) -> Invite | None:
        """Insert an invite that expires ``ttl`` after now, by the database clock.

        Args:
            code: The new code.
            created_by: Telegram ID of the creating user, who must already exist.
            ttl: How long the code works.

        Returns:
            The new invite, or ``None`` if the code is already taken.
        """
        statement = (
            insert(Invite)
            .values(code=code, created_by=created_by, expires_at=func.now() + ttl)
            # A taken code is skipped instead of raising, which would abort the transaction.
            .on_conflict_do_nothing(index_elements=[Invite.code])
            .returning(Invite)
        )
        return await self._session.scalar(statement)

    async def lock_usable(self, code: str) -> int | None:
        """Lock the code's row if it is unused and unexpired, until the transaction ends.

        A concurrent caller with the same code waits for the lock. Once the first
        transaction commits, Postgres re-checks the row, sees it used and returns nothing.

        Returns:
            The Telegram ID of the code's creator, or ``None`` if the code is unknown,
            used or expired.
        """
        statement = (
            select(Invite.created_by)
            .where(Invite.code == code, Invite.used_at.is_(None), Invite.expires_at > func.now())
            .with_for_update()
        )
        return await self._session.scalar(statement)

    async def mark_used(self, code: str, used_by: int) -> None:
        """Mark an unused code as used now by ``used_by``; a used code is left as it is."""
        statement = (
            update(Invite)
            # After lock_usable this always matches; the guard keeps a used code's record.
            .where(Invite.code == code, Invite.used_at.is_(None))
            .values(used_at=func.now(), used_by=used_by)
        )
        await self._session.execute(statement)
