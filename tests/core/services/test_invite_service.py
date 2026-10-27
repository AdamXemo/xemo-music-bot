import asyncio
from collections.abc import AsyncIterator, Callable

import pytest
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from xemo_music_bot.core.services.invites import (
    InviteService,
    JoinResult,
    JoinStatus,
    generate_code,
    is_code_format,
)
from xemo_music_bot.db.models import Invite, User
from xemo_music_bot.db.repositories.invites import InvitesRepository
from xemo_music_bot.db.repositories.users import UsersRepository
from xemo_music_bot.db.session import create_session_factory

ADMIN_ID = 1
FRIEND_ID = 2
OTHER_ID = 3


def make_service(
    session: AsyncSession, generate: Callable[[], str] = generate_code
) -> InviteService:
    return InviteService(InvitesRepository(session), UsersRepository(session), generate)


@pytest.fixture
async def service(session: AsyncSession) -> InviteService:
    await session.execute(insert(User).values(tg_id=ADMIN_ID))
    return make_service(session)


async def used_by(session: AsyncSession, code: str) -> int | None:
    return await session.scalar(select(Invite.used_by).where(Invite.code == code))


def test_generated_codes_have_the_code_format() -> None:
    assert is_code_format(generate_code())


async def test_join_with_a_fresh_code_creates_the_user_and_uses_the_code(
    service: InviteService, session: AsyncSession
) -> None:
    invite = await service.create(ADMIN_ID)

    result = await service.join(invite.code, FRIEND_ID, "anna", "uk")

    assert (result.status, result.inviter_id) == (JoinStatus.JOINED, ADMIN_ID)
    session.expunge_all()  # read back from Postgres, not the identity map
    user = await session.get(User, FRIEND_ID)
    assert user is not None
    assert (user.username, user.language, user.invited_by, user.language_chosen) == (
        "anna",
        "uk",
        ADMIN_ID,
        False,
    )
    assert await used_by(session, invite.code) == FRIEND_ID


async def test_second_person_with_a_used_code_is_refused(
    service: InviteService, session: AsyncSession
) -> None:
    invite = await service.create(ADMIN_ID)
    await service.join(invite.code, FRIEND_ID, None, "en")

    result = await service.join(invite.code, OTHER_ID, None, "en")

    assert result == JoinResult(JoinStatus.INVALID, None)
    assert await session.get(User, OTHER_ID) is None


async def test_existing_user_is_already_a_member_and_the_code_stays_unused(
    service: InviteService, session: AsyncSession
) -> None:
    # The row appeared after the caller's access check, so the join finds it.
    await session.execute(insert(User).values(tg_id=FRIEND_ID))
    invite = await service.create(ADMIN_ID)

    result = await service.join(invite.code, FRIEND_ID, None, "en")

    assert result == JoinResult(JoinStatus.ALREADY_MEMBER, None)
    assert await used_by(session, invite.code) is None


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("", id="empty"),
        pytest.param("Kx7pQ2m", id="too-short"),
        pytest.param("Kx7pQ2m-", id="dash"),
        pytest.param("Kx7pQ 2m", id="space"),
        pytest.param("Kx7pQ2mZ\n", id="trailing-newline"),
        # str.isalnum() would accept this digit; the code format does not.
        pytest.param("Kx7pQ2m\N{ARABIC-INDIC DIGIT ONE}", id="non-ascii-digit"),
    ],
)
async def test_malformed_code_is_invalid_without_a_query(
    unreachable_engine: AsyncEngine, code: str
) -> None:
    # Any query on this session would fail, which proves none is made.
    async with AsyncSession(unreachable_engine) as session:
        result = await make_service(session).join(code, FRIEND_ID, None, "en")

    assert result.status is JoinStatus.INVALID


async def test_create_retries_with_a_new_code_when_one_is_taken(
    service: InviteService, session: AsyncSession
) -> None:
    await make_service(session, lambda: "TakenAAA").create(ADMIN_ID)
    codes = iter(["TakenAAA", "FreshBBB"])

    invite = await make_service(session, lambda: next(codes)).create(ADMIN_ID)

    assert invite.code == "FreshBBB"


async def test_create_gives_up_after_three_taken_codes(
    service: InviteService, session: AsyncSession
) -> None:
    await make_service(session, lambda: "TakenAAA").create(ADMIN_ID)
    calls: list[str] = []

    def taken() -> str:
        calls.append("TakenAAA")
        return "TakenAAA"

    with pytest.raises(RuntimeError, match="No free invite code"):
        await make_service(session, taken).create(ADMIN_ID)
    assert len(calls) == 3


# The race tests commit for real, on separate connections, so they use the engine rather
# than the rolled-back `session` fixture and delete their rows afterwards.


@pytest.fixture
def factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
async def committed_code(
    engine: AsyncEngine, factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[str]:
    try:
        async with factory() as session:
            await session.execute(insert(User).values(tg_id=ADMIN_ID))
            invite = await make_service(session).create(ADMIN_ID)
            await session.commit()
        yield invite.code
    finally:
        # Other tests expect empty tables; deleting the users cascades to their invites.
        async with engine.begin() as connection:
            await connection.execute(
                delete(User).where(User.tg_id.in_([ADMIN_ID, FRIEND_ID, OTHER_ID]))
            )


async def join_and_commit(
    factory: async_sessionmaker[AsyncSession], code: str, tg_id: int
) -> JoinStatus:
    async with factory() as session:
        result = await make_service(session).join(code, tg_id, None, "en")
        # Holding the row lock a moment makes the other join wait on it.
        await asyncio.sleep(0.05)
        await session.commit()
        return result.status


async def test_two_strangers_racing_for_one_code_let_only_one_in(
    factory: async_sessionmaker[AsyncSession], committed_code: str
) -> None:
    statuses = await asyncio.gather(
        join_and_commit(factory, committed_code, FRIEND_ID),
        join_and_commit(factory, committed_code, OTHER_ID),
    )

    assert sorted(statuses) == sorted([JoinStatus.JOINED, JoinStatus.INVALID])
    async with factory() as session:
        joined = await session.scalars(select(User.tg_id).where(User.tg_id != ADMIN_ID))
        assert len(joined.all()) == 1


async def test_one_stranger_tapping_twice_joins_once(
    factory: async_sessionmaker[AsyncSession], committed_code: str
) -> None:
    statuses = await asyncio.gather(
        join_and_commit(factory, committed_code, FRIEND_ID),
        join_and_commit(factory, committed_code, FRIEND_ID),
    )

    assert sorted(statuses) == sorted([JoinStatus.JOINED, JoinStatus.ALREADY_MEMBER])
    async with factory() as session:
        assert await used_by(session, committed_code) == FRIEND_ID
