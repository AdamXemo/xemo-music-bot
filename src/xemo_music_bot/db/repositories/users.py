"""Reads and writes rows of the ``users`` table."""

from collections.abc import Collection

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.core.models import Language
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

    async def get_languages(self, tg_ids: Collection[int]) -> dict[int, Language]:
        """Return the stored language of each given user who has a row, in one query.

        Args:
            tg_ids: Telegram user IDs; those without a row are left out of the result.
        """
        statement = select(User.tg_id, User.language).where(User.tg_id.in_(tg_ids))
        return {row.tg_id: row.language for row in await self._session.execute(statement)}

    async def create(
        self,
        tg_id: int,
        username: str | None,
        language: Language,
        invited_by: int | None = None,
    ) -> User | None:
        """Insert a user unless one with this Telegram ID already exists.

        A duplicate is skipped inside Postgres instead of raising, because an
        IntegrityError would abort the whole transaction, and two taps on the same
        invite link can race.

        Args:
            tg_id: Telegram user ID.
            username: Telegram username without the leading "@", if the user has one.
            language: The language the bot speaks to the user.
            invited_by: Telegram ID of the inviting user, who must already exist.

        Returns:
            The new user, or ``None`` if the user already existed (left unchanged).

        Raises:
            sqlalchemy.exc.IntegrityError: The inviter does not exist, or a CHECK
                constraint failed (self-invite, non-positive ID).
        """
        statement = (
            insert(User)
            .values(tg_id=tg_id, username=username, language=language, invited_by=invited_by)
            # Skip only a duplicate tg_id. Naming the target keeps any future unique
            # constraint loud; FK and CHECK violations always raise.
            .on_conflict_do_nothing(index_elements=[User.tg_id])
            # RETURNING yields no row when the insert was skipped, hence None.
            .returning(User)
        )
        return await self._session.scalar(statement)

    async def set_language(self, tg_id: int, language: Language) -> User | None:
        """Change the user's language in one atomic UPDATE and mark it as chosen.

        Every call is the user's own pick, so it also sets ``language_chosen``. The ORM
        applies the new values to the user's object if this session already holds it, so
        a ``db_user`` loaded earlier in the same update stays current.

        Args:
            tg_id: Telegram user ID.
            language: The new language.

        Returns:
            The updated user, or ``None`` if no user has this Telegram ID.
        """
        statement = (
            update(User)
            .where(User.tg_id == tg_id)
            .values(language=language, language_chosen=True)
            .returning(User)
        )
        return (await self._session.scalars(statement)).one_or_none()
