"""Change the language the bot speaks to a user (ADR 0005)."""

from collections.abc import Collection

from xemo_music_bot.core.models import Language
from xemo_music_bot.db.models import User
from xemo_music_bot.db.repositories.users import UsersRepository


class LanguageService:
    """Stores a user's language choice within the caller's session.

    Args:
        users: Repository bound to the current update's session.
    """

    def __init__(self, users: UsersRepository) -> None:
        self._users = users

    async def get_languages(self, tg_ids: Collection[int]) -> dict[int, Language]:
        """Return the stored language of each given user who has a row.

        Args:
            tg_ids: Telegram user IDs; those without a row are left out of the result.
        """
        return await self._users.get_languages(tg_ids)

    async def set_language(self, tg_id: int, language: Language) -> User:
        """Store ``language`` as the user's language.

        Args:
            tg_id: Telegram user ID of a user who has a row.
            language: The language the user picked.

        Returns:
            The updated user.

        Raises:
            LookupError: No user has this Telegram ID.
        """
        user = await self._users.set_language(tg_id, language)
        if user is None:
            raise LookupError(f"No user with tg_id {tg_id}")
        return user
