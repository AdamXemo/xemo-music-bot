import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from xemo_music_bot.config import get_settings
from xemo_music_bot.db.redis import create_redis
from xemo_music_bot.db.session import create_db_engine

SETTINGS_ENV_VARS = (
    "BOT_TOKEN",
    "ADMIN_IDS",
    "LOG_LEVEL",
    "LOG_TIMINGS",
    "DATABASE_URL",
    "REDIS_URL",
)
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
# Port 1 refuses at once, so code that touches this database fails fast and visibly.
UNREACHABLE_DATABASE_URL = "postgresql+asyncpg://xemo:not-logged@127.0.0.1:1/xemo"
# Port 1 refuses at once, like the database one above.
UNREACHABLE_REDIS_URL = "redis://:not-logged@127.0.0.1:1/0"


@pytest.fixture(autouse=True)
def isolated_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    """Keep tests independent of the developer's shell and local `.env`."""
    for name in SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # Settings reads `.env` relative to the working directory; an empty dir has none.
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def unreachable_engine() -> AsyncIterator[AsyncEngine]:
    """Engine for a database that does not exist, for tests that must not need Postgres."""
    engine = create_db_engine(UNREACHABLE_DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    """URL of a disposable test database, or skip when none is configured.

    Deliberately not DATABASE_URL: these tests drop tables, so they must never run
    against the development database by accident.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        # In CI a missing URL is a broken workflow, not a choice; a skip would hide it.
        if os.environ.get("CI"):
            pytest.fail("TEST_DATABASE_URL must be set in CI")
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture(scope="session")
def alembic_config(database_url: str) -> Config:
    """Alembic configuration pointing at the test database."""
    config = Config(ALEMBIC_INI)
    config.attributes["configure_logger"] = False
    # The ini parser treats "%" as interpolation, and URL-encoded passwords contain it.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


# Sync on purpose: migrations/env.py calls asyncio.run, which cannot nest in a running loop.
@pytest.fixture(scope="session")
def migrated_url(database_url: str, alembic_config: Config) -> str:
    """Test database URL with the schema at head, migrated once per test run.

    The migration round trip test also ends at head, so test order does not matter.
    """
    command.upgrade(alembic_config, "head")
    return database_url


@pytest.fixture
async def engine(migrated_url: str) -> AsyncIterator[AsyncEngine]:
    """Engine for the migrated test database.

    Per test, because asyncpg connections belong to the event loop that opened them
    and every test gets its own loop.
    """
    engine = create_db_engine(migrated_url)
    yield engine
    await engine.dispose()


@pytest.fixture
async def connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """Connection inside a transaction that is rolled back after the test."""
    async with engine.connect() as connection:
        await connection.begin()
        yield connection
        await connection.rollback()


@pytest.fixture
async def session(connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """Session whose commits become savepoints, so the test's rollback undoes them."""
    async with AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as session:
        yield session


@pytest.fixture(scope="session")
def redis_url() -> str:
    """URL of a disposable Redis database index, or skip when none is configured.

    Deliberately not REDIS_URL: the `redis` fixture flushes the index, so it must never
    run against the development one by accident.
    """
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        # In CI a missing URL is a broken workflow, not a choice; a skip would hide it.
        if os.environ.get("CI"):
            pytest.fail("TEST_REDIS_URL must be set in CI")
        pytest.skip("TEST_REDIS_URL is not set")
    # Index 0 (also the default when the URL names none) is the bot's own; flushing it
    # would wipe live search sessions.
    if urlparse(url).path.strip("/") in ("", "0"):
        pytest.fail("TEST_REDIS_URL must name a non-zero database index, e.g. /15")
    return url


@pytest.fixture
async def redis(redis_url: str) -> AsyncIterator[Redis]:
    """Client for the test Redis index, emptied before each test.

    Per test, because connections belong to the event loop that opened them.
    """
    client = create_redis(redis_url)
    await client.flushdb()
    yield client
    await client.aclose()


@pytest.fixture
async def unreachable_redis() -> AsyncIterator[Redis]:
    """Client for a Redis that does not exist, for tests that must not need one."""
    client = create_redis(UNREACHABLE_REDIS_URL)
    yield client
    await client.aclose()
