"""Async engine and session factory construction.

Nothing here is a module-level global: the entrypoint builds one engine and one session
factory at startup and passes them to whatever needs them.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_db_engine(url: str) -> AsyncEngine:
    """Create the application's async engine with a connection pool.

    Args:
        url: SQLAlchemy URL with an async driver, e.g. ``postgresql+asyncpg://...``.

    Returns:
        An engine; the caller must ``await engine.dispose()`` on shutdown.
    """
    # pre_ping replaces connections Postgres closed while idle (restarts, timeouts)
    # instead of failing the first query after a quiet period.
    return create_async_engine(url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a factory for sessions bound to ``engine``.

    Args:
        engine: The engine returned by :func:`create_db_engine`.

    Returns:
        A session factory; use each session as ``async with factory() as session:``.
    """
    # Objects stay readable after commit: refreshing expired attributes would need an
    # implicit lazy load, which raises under asyncio.
    return async_sessionmaker(engine, expire_on_commit=False)
