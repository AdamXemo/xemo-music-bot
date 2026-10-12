"""Alembic environment: runs migrations against Postgres through the async engine."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from xemo_music_bot.config import get_settings
from xemo_music_bot.db.models import Base

config = context.config
target_metadata = Base.metadata

# Tests turn this off so running migrations does not reconfigure pytest's logging.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    # Keep loggers created before this point (the app's) working.
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def database_url() -> str:
    """Return the URL set on the Alembic config (tests do this), else DATABASE_URL."""
    return (
        config.get_main_option("sqlalchemy.url") or get_settings().database_url.get_secret_value()
    )


def run_migrations_offline() -> None:
    """Emit the migration SQL to stdout without connecting (``alembic upgrade --sql``)."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run the migrations on an open connection, inside one transaction."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Off by default in Alembic; without it a changed DEFAULT would not be migrated
        # and the drift check in tests would miss it.
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Connect with a throwaway engine and run the migrations through it."""
    # NullPool: a one-off command has no use for pooled connections after it exits.
    engine = create_async_engine(database_url(), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
