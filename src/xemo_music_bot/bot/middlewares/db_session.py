"""One database session per update, committed after the handler."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    """Put a session into ``data["session"]`` and own its transaction.

    Repositories never commit; this middleware commits once after the handler
    returns, so each update is one transaction. The session connects lazily, so
    updates that never query cost no connection.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Run the handler inside a session and commit if it returns.

        If the handler raises, leaving the ``async with`` block rolls back and the
        exception reaches aiogram's error handling. Error handlers therefore get a
        closed, rolled-back session and must not write through it (the Error UX item
        decides the real handling).
        """
        async with self._session_factory() as session:
            data["session"] = session
            result = await handler(event, data)
            await session.commit()
            return result
