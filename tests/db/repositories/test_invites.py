from datetime import timedelta

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from xemo_music_bot.db.models import Invite, User
from xemo_music_bot.db.repositories.invites import InvitesRepository

ADMIN_ID = 1
FRIEND_ID = 2
CODE = "Kx7pQ2mZ"
WEEK = timedelta(days=7)


@pytest.fixture
async def invites(session: AsyncSession) -> InvitesRepository:
    await session.execute(insert(User), [{"tg_id": ADMIN_ID}, {"tg_id": FRIEND_ID}])
    return InvitesRepository(session)


async def test_create_expires_after_the_ttl_and_is_unused(invites: InvitesRepository) -> None:
    invite = await invites.create(CODE, ADMIN_ID, WEEK)

    assert invite is not None
    assert invite.expires_at - invite.created_at == WEEK
    assert (invite.code, invite.created_by, invite.used_at, invite.used_by) == (
        CODE,
        ADMIN_ID,
        None,
        None,
    )


async def test_create_with_a_taken_code_returns_none_and_keeps_the_first(
    invites: InvitesRepository, session: AsyncSession
) -> None:
    await invites.create(CODE, ADMIN_ID, WEEK)

    assert await invites.create(CODE, FRIEND_ID, timedelta(days=1)) is None

    session.expunge_all()  # read back from Postgres, not the identity map
    first = await session.get(Invite, CODE)
    assert first is not None
    assert first.created_by == ADMIN_ID
    assert first.expires_at - first.created_at == WEEK


async def test_lock_usable_returns_the_creator_of_a_working_code(
    invites: InvitesRepository,
) -> None:
    await invites.create(CODE, ADMIN_ID, WEEK)

    assert await invites.lock_usable(CODE) == ADMIN_ID


@pytest.mark.parametrize("state", ["unknown", "used", "expired"])
async def test_lock_usable_refuses_a_code_that_does_not_work(
    invites: InvitesRepository, session: AsyncSession, state: str
) -> None:
    if state == "used":
        await invites.create(CODE, ADMIN_ID, WEEK)
        await invites.mark_used(CODE, FRIEND_ID)
    elif state == "expired":
        # Inserted directly: the repository only creates codes that expire in the future.
        await session.execute(
            insert(Invite).values(
                code=CODE,
                created_by=ADMIN_ID,
                created_at=func.now() - timedelta(days=8),
                expires_at=func.now() - timedelta(days=1),
            )
        )

    assert await invites.lock_usable(CODE) is None


async def test_mark_used_records_who_and_when(
    invites: InvitesRepository, session: AsyncSession
) -> None:
    await invites.create(CODE, ADMIN_ID, WEEK)

    await invites.mark_used(CODE, FRIEND_ID)

    used_by, used_at = (await session.execute(select(Invite.used_by, Invite.used_at))).one()
    assert used_by == FRIEND_ID
    assert used_at is not None


@pytest.mark.parametrize(
    "code",
    [
        pytest.param("Kx7pQ2m", id="too-short"),
        pytest.param("Kx7pQ2mZ9", id="too-long"),
        pytest.param("Kx7pQ2m_", id="underscore"),
        pytest.param("Kx7pQ2m\N{LATIN SMALL LETTER E WITH ACUTE}", id="non-ascii-letter"),
    ],
)
async def test_create_refuses_a_malformed_code(invites: InvitesRepository, code: str) -> None:
    with pytest.raises(IntegrityError, match="ck_invites_code_format"):
        await invites.create(code, ADMIN_ID, WEEK)


# The repository never writes these rows, so the two CHECKs are hit by direct inserts.


async def test_database_refuses_an_invite_that_expires_when_created(
    invites: InvitesRepository, session: AsyncSession
) -> None:
    with pytest.raises(IntegrityError, match="ck_invites_expires_after_created"):
        await session.execute(
            insert(Invite).values(code=CODE, created_by=ADMIN_ID, expires_at=func.now())
        )


async def test_database_refuses_a_user_without_a_time_of_use(
    invites: InvitesRepository, session: AsyncSession
) -> None:
    with pytest.raises(IntegrityError, match="ck_invites_used_by_needs_used_at"):
        await session.execute(
            insert(Invite).values(
                code=CODE, created_by=ADMIN_ID, expires_at=func.now() + WEEK, used_by=FRIEND_ID
            )
        )
