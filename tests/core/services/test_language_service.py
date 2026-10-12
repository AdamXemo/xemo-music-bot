import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.core.services.language import LanguageService
from xemo_music_bot.db.repositories.users import UsersRepository


@pytest.fixture
def users(session: AsyncSession) -> UsersRepository:
    return UsersRepository(session)


async def test_set_language_returns_the_updated_user(users: UsersRepository) -> None:
    await users.create(1, "friend", "en")

    user = await LanguageService(users).set_language(1, "uk")

    assert (user.tg_id, user.language) == (1, "uk")


async def test_set_language_for_unknown_user_raises(users: UsersRepository) -> None:
    with pytest.raises(LookupError, match="No user with tg_id 1"):
        await LanguageService(users).set_language(1, "uk")
