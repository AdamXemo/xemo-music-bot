import pytest
from sqlalchemy import delete, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
    await users.create(1, "inviter")
    created = await users.create(2, "friend", invited_by=1)

    assert created is not None
    assert (created.tg_id, created.username, created.role, created.invited_by) == (
        2,
        "friend",
        "user",
        1,
    )
    assert created.created_at is not None
    assert await users.get(2) is created
    session.expunge_all()  # read back from Postgres, not the identity map
    user = await users.get(2)
    assert user is not None
    assert (user.username, user.role, user.invited_by) == ("friend", "user", 1)
    assert user.created_at is not None


async def test_create_skips_existing_user_and_leaves_it_unchanged(
    users: UsersRepository, session: AsyncSession
) -> None:
    await users.create(1, "original")

    assert await users.create(1, "renamed") is None
    session.expunge_all()
    user = await users.get(1)
    assert user is not None
    assert user.username == "original"


async def test_create_rejects_unknown_inviter(users: UsersRepository) -> None:
    with pytest.raises(IntegrityError, match="fk_users_invited_by_users"):
        await users.create(2, "friend", invited_by=1)


async def test_create_rejects_self_invite(users: UsersRepository) -> None:
    with pytest.raises(IntegrityError, match="ck_users_not_self_invited"):
        await users.create(1, "friend", invited_by=1)


async def test_create_rejects_non_positive_tg_id(users: UsersRepository) -> None:
    with pytest.raises(IntegrityError, match="ck_users_tg_id_positive"):
        await users.create(0, "friend")


@pytest.mark.parametrize("role", ["owner", "admin"])
async def test_unknown_role_is_rejected(session: AsyncSession, role: str) -> None:
    # 'admin' too: admin rights come only from config, never from a row.
    with pytest.raises(IntegrityError, match="ck_users_role_valid"):
        await session.execute(insert(User).values(tg_id=1, role=role))


async def test_deleting_inviter_keeps_invited_user(
    users: UsersRepository, session: AsyncSession
) -> None:
    await users.create(1, "inviter")
    await users.create(2, "friend", invited_by=1)

    await session.execute(delete(User).where(User.tg_id == 1))
    session.expire_all()

    user = await users.get(2)
    assert user is not None
    assert user.invited_by is None
