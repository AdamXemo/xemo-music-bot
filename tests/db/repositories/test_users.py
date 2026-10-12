from typing import get_args

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.core.models import Language
from xemo_music_bot.db.models import User
from xemo_music_bot.db.repositories.users import UsersRepository

# Each IntegrityError test triggers exactly one violation: Postgres aborts the
# transaction after it, and the fixtures roll the whole test back afterwards.


@pytest.fixture
def users(session: AsyncSession) -> UsersRepository:
    return UsersRepository(session)


async def test_get_returns_none_for_unknown_user(users: UsersRepository) -> None:
    assert await users.get(1) is None


async def test_create_stores_user_with_defaults(
    users: UsersRepository, session: AsyncSession
) -> None:
    await users.create(1, "inviter", "en")
    created = await users.create(2, "friend", "uk", invited_by=1)

    assert created is not None
    assert (
        created.tg_id,
        created.username,
        created.language,
        created.role,
        created.invited_by,
    ) == (2, "friend", "uk", "user", 1)
    assert created.created_at is not None
    assert await users.get(2) is created
    session.expunge_all()  # read back from Postgres, not the identity map
    user = await users.get(2)
    assert user is not None
    assert (user.username, user.language, user.role, user.invited_by) == (
        "friend",
        "uk",
        "user",
        1,
    )
    assert user.created_at is not None


async def test_create_skips_existing_user_and_leaves_it_unchanged(
    users: UsersRepository, session: AsyncSession
) -> None:
    await users.create(1, "original", "uk")

    assert await users.create(1, "renamed", "ru") is None
    session.expunge_all()
    user = await users.get(1)
    assert user is not None
    assert (user.username, user.language) == ("original", "uk")


async def test_create_rejects_unknown_inviter(users: UsersRepository) -> None:
    with pytest.raises(IntegrityError, match="fk_users_invited_by_users"):
        await users.create(2, "friend", "en", invited_by=1)


async def test_create_rejects_self_invite(users: UsersRepository) -> None:
    with pytest.raises(IntegrityError, match="ck_users_not_self_invited"):
        await users.create(1, "friend", "en", invited_by=1)


async def test_create_rejects_non_positive_tg_id(users: UsersRepository) -> None:
    with pytest.raises(IntegrityError, match="ck_users_tg_id_positive"):
        await users.create(0, "friend", "en")


@pytest.mark.parametrize("role", ["owner", "admin"])
async def test_unknown_role_is_rejected(session: AsyncSession, role: str) -> None:
    # 'admin' too: admin rights come only from config, never from a row.
    with pytest.raises(IntegrityError, match="ck_users_role_valid"):
        await session.execute(insert(User).values(tg_id=1, role=role))


async def test_unknown_language_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_users_language_valid"):
        await session.execute(insert(User).values(tg_id=1, language="de"))


async def test_row_without_language_gets_english(session: AsyncSession) -> None:
    await session.execute(insert(User).values(tg_id=1))

    assert await session.scalar(select(User.language).where(User.tg_id == 1)) == "en"


# Guards drift between the Language literal and the CHECK constraint's literal SQL.
# It only catches a Language value the CHECK rejects; an extra CHECK value is harmless.
@pytest.mark.parametrize("language", get_args(Language))
async def test_every_supported_language_is_accepted(
    users: UsersRepository, language: Language
) -> None:
    created = await users.create(1, "friend", language)

    assert created is not None
    assert created.language == language


async def test_set_language_updates_the_stored_row(
    users: UsersRepository, session: AsyncSession
) -> None:
    await users.create(1, "friend", "en")

    updated = await users.set_language(1, "ru")

    assert updated is not None
    assert updated.language == "ru"
    session.expunge_all()
    user = await users.get(1)
    assert user is not None
    assert user.language == "ru"


async def test_set_language_refreshes_the_user_already_in_the_session(
    users: UsersRepository,
) -> None:
    db_user = await users.create(1, "friend", "en")

    await users.set_language(1, "uk")

    # The middleware's db_user must not keep serving the old catalog after a switch.
    assert db_user is not None
    assert db_user.language == "uk"


async def test_set_language_returns_none_for_unknown_user(users: UsersRepository) -> None:
    assert await users.set_language(1, "uk") is None


async def test_deleting_inviter_keeps_invited_user(
    users: UsersRepository, session: AsyncSession
) -> None:
    await users.create(1, "inviter", "en")
    await users.create(2, "friend", "en", invited_by=1)

    await session.execute(delete(User).where(User.tg_id == 1))
    session.expire_all()

    user = await users.get(2)
    assert user is not None
    assert user.invited_by is None
