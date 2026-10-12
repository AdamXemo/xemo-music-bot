import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.core.services.access import AccessService, AccessStatus
from xemo_music_bot.db.models import User
from xemo_music_bot.db.repositories.users import UsersRepository

ADMIN_ID = 1


@pytest.fixture
def users(session: AsyncSession) -> UsersRepository:
    return UsersRepository(session)


@pytest.fixture
def service(users: UsersRepository) -> AccessService:
    return AccessService(users, admin_ids=frozenset({ADMIN_ID}))


async def count_users(session: AsyncSession) -> int | None:
    return await session.scalar(select(func.count()).select_from(User))


async def test_unknown_user_is_a_stranger_and_not_stored(
    service: AccessService, session: AsyncSession
) -> None:
    access = await service.check(2, "stranger")

    assert (access.status, access.user, access.allowed) == (AccessStatus.STRANGER, None, False)
    assert await count_users(session) == 0


async def test_user_row_makes_a_member(service: AccessService, users: UsersRepository) -> None:
    await users.create(2, "friend")

    access = await service.check(2, "friend")

    assert access.status is AccessStatus.MEMBER
    assert access.allowed
    assert access.user is not None
    assert access.user.tg_id == 2


async def test_blocked_role_makes_blocked(service: AccessService, session: AsyncSession) -> None:
    await session.execute(insert(User).values(tg_id=2, role="blocked"))

    access = await service.check(2, None)

    assert access.status is AccessStatus.BLOCKED
    assert not access.allowed


async def test_config_admin_without_row_gets_one_created(
    service: AccessService, session: AsyncSession
) -> None:
    access = await service.check(ADMIN_ID, "owner")

    assert access.status is AccessStatus.ADMIN
    assert access.allowed
    session.expunge_all()  # read back from Postgres, not the identity map
    user = await session.get(User, ADMIN_ID)
    assert user is not None
    assert (user.username, user.role, user.invited_by) == ("owner", "user", None)


async def test_config_admin_with_row_keeps_it_unchanged(
    service: AccessService, users: UsersRepository, session: AsyncSession
) -> None:
    await users.create(ADMIN_ID, "original")

    access = await service.check(ADMIN_ID, "renamed")

    assert access.status is AccessStatus.ADMIN
    assert await count_users(session) == 1
    session.expunge_all()
    user = await session.get(User, ADMIN_ID)
    assert user is not None
    assert user.username == "original"


async def test_config_admin_cannot_be_blocked(
    service: AccessService, session: AsyncSession
) -> None:
    await session.execute(insert(User).values(tg_id=ADMIN_ID, role="blocked"))

    access = await service.check(ADMIN_ID, None)

    assert access.status is AccessStatus.ADMIN
    assert access.allowed
    # The check only reads the role; it never rewrites it.
    assert access.user is not None
    assert access.user.role == "blocked"


class RacingUsers(UsersRepository):
    """A concurrent update inserted the row between our read and our insert."""

    def __init__(self, winner: User | None) -> None:
        self._winner = winner
        self.reads = 0

    async def get(self, tg_id: int) -> User | None:
        self.reads += 1
        # First read: no row yet; the read after the skipped insert sees the winner's row.
        return None if self.reads == 1 else self._winner

    async def create(
        self, tg_id: int, username: str | None, invited_by: int | None = None
    ) -> User | None:
        return None


async def test_config_admin_falls_back_to_the_row_a_concurrent_update_created() -> None:
    winner = User(tg_id=ADMIN_ID, role="user")
    service = AccessService(RacingUsers(winner), admin_ids=frozenset({ADMIN_ID}))

    access = await service.check(ADMIN_ID, None)

    assert access.status is AccessStatus.ADMIN
    assert access.user is winner


async def test_config_admin_row_missing_after_insert_raises() -> None:
    service = AccessService(RacingUsers(None), admin_ids=frozenset({ADMIN_ID}))

    with pytest.raises(RuntimeError, match="could not be created or read"):
        await service.check(ADMIN_ID, None)
