"""Reads and writes rows of the ``users`` table."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.db.models import User


class UsersRepository:
    """Queries for :class:`User` within the caller's session.

    It never commits: whoever opened the session owns the transaction (the bot's
    session middleware commits once per update).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tg_id: int) -> User | None:
        """Return the user with this Telegram ID, or ``None`` if they never joined."""
        return await self._session.get(User, tg_id)

    async def create(
        self, tg_id: int, username: str | None, invited_by: int | None = None
    ) -> User | None:
        """Insert a user unless one with this Telegram ID already exists.

        A duplicate is skipped inside Postgres instead of raising, because an
        IntegrityError would abort the whole transaction, and two taps on the same
        invite link can race.

        Args:
            tg_id: Telegram user ID.
            username: Telegram username without the leading "@", if the user has one.
            invited_by: Telegram ID of the inviting user, who must already exist.

        Returns:
            The new user, or ``None`` if the user already existed (left unchanged).

        Raises:
            sqlalchemy.exc.IntegrityError: The inviter does not exist, or a CHECK
                constraint failed (self-invite, non-positive ID).
        """
        statement = (
            insert(User)
            .values(tg_id=tg_id, username=username, invited_by=invited_by)
            # Skip only a duplicate tg_id. Naming the target keeps any future unique
            # constraint loud; FK and CHECK violations always raise.
            .on_conflict_do_nothing(index_elements=[User.tg_id])
            # RETURNING yields no row when the insert was skipped, hence None.
            .returning(User)
        )
        return await self._session.scalar(statement)
