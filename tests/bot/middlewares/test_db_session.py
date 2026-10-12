from typing import Any

import pytest
from aiogram.types import TelegramObject, Update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from xemo_music_bot.bot.middlewares.db_session import DbSessionMiddleware
from xemo_music_bot.db.models import User
from xemo_music_bot.db.repositories.users import UsersRepository


@pytest.fixture
def middleware(connection: AsyncConnection) -> DbSessionMiddleware:
    # Commits become savepoints on the test connection, so the test can see them and
    # the connection fixture still rolls everything back.
    factory = async_sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    return DbSessionMiddleware(factory)


async def stored_ids(connection: AsyncConnection) -> list[int]:
    return list(await connection.scalars(select(User.tg_id)))


async def test_commits_what_the_handler_wrote(
    middleware: DbSessionMiddleware, connection: AsyncConnection
) -> None:
    async def handler(event: TelegramObject, data: dict[str, Any]) -> str:
        assert isinstance(data["session"], AsyncSession)
        await UsersRepository(data["session"]).create(1, "friend")
        return "handled"

    result = await middleware(handler, Update(update_id=1), {})

    assert result == "handled"
    assert await stored_ids(connection) == [1]


async def test_rolls_back_and_reraises_when_the_handler_fails(
    middleware: DbSessionMiddleware, connection: AsyncConnection
) -> None:
    async def handler(event: TelegramObject, data: dict[str, Any]) -> None:
        await UsersRepository(data["session"]).create(1, "friend")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await middleware(handler, Update(update_id=1), {})

    assert await stored_ids(connection) == []
