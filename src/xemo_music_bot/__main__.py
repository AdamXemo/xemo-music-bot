"""Entrypoint: `python -m xemo_music_bot` or the `xemo-music-bot` script."""

import logging
from functools import partial

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from xemo_music_bot import timing
from xemo_music_bot.bot.commands import publish_commands
from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.config import Settings, get_settings
from xemo_music_bot.core.services.delivery import DeliveryService
from xemo_music_bot.core.services.search import SearchService
from xemo_music_bot.db.redis import check_connection as check_redis_connection
from xemo_music_bot.db.redis import create_redis
from xemo_music_bot.db.repositories.search_sessions import SearchSessionsRepository
from xemo_music_bot.db.repositories.tracks import TracksRepository
from xemo_music_bot.db.session import check_connection, create_db_engine, create_session_factory
from xemo_music_bot.logging_setup import setup_logging
from xemo_music_bot.providers.soundcloud import MAX_DURATION, SoundCloudProvider

logger = logging.getLogger(__name__)


async def check_database(engine: AsyncEngine) -> None:
    """Stop at startup if Postgres is unreachable, instead of failing on the first update.

    Args:
        engine: The application's engine.

    Raises:
        SystemExit: The database cannot be reached; the cause is logged first.
    """
    try:
        await check_connection(engine)
    except (OSError, SQLAlchemyError) as error:
        # The driver message names the cause (refused, bad password) but not the URL.
        logger.error(
            "Cannot connect to Postgres - is it running and is DATABASE_URL right? %s", error
        )
        raise SystemExit(1) from None


async def close_database(engine: AsyncEngine) -> None:
    """Close the engine's pooled connections when polling stops."""
    await engine.dispose()


async def check_redis(redis: Redis) -> None:
    """Stop at startup if Redis is unreachable, instead of failing on the first search.

    Args:
        redis: The application's Redis client.

    Raises:
        SystemExit: Redis cannot be reached; the cause is logged first.
    """
    try:
        await check_redis_connection(redis)
    except (OSError, RedisError) as error:
        # The error names the cause (refused, bad password) but not the URL.
        logger.error("Cannot connect to Redis - is it running and is REDIS_URL right? %s", error)
        raise SystemExit(1) from None


async def close_redis(redis: Redis) -> None:
    """Close the client's pooled connections when polling stops."""
    await redis.aclose()


def main() -> None:
    """Load settings, configure logging and run the bot with long polling until stopped."""
    settings = get_settings()
    live_console = timing.configure(settings.log_timings)
    # Around all of startup too: a failure such as a malformed token must not leave the
    # terminal's cursor hidden by the live timings display.
    try:
        setup_logging(settings.log_level, live_console)
        _run(settings)
    finally:
        timing.close()


def _run(settings: Settings) -> None:
    """Build the bot, its services and dispatcher, then poll until stopped."""
    logger.info("Settings loaded, %d admin(s) configured", len(settings.admin_ids))
    # HTML for every message (MVP spec): custom emoji slots render as <tg-emoji> tags.
    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    engine = create_db_engine(settings.database_url.get_secret_value())
    session_factory = create_session_factory(engine)
    redis = create_redis(settings.redis_url.get_secret_value())
    provider = SoundCloudProvider()
    search_service = SearchService(provider, SearchSessionsRepository(redis))
    delivery_service = DeliveryService(provider, TracksRepository(session_factory), MAX_DURATION)
    dispatcher = build_dispatcher(
        session_factory, settings.admin_ids, search_service, delivery_service
    )
    # partial binds the leading arguments; aiogram calls hooks only with the arguments they
    # declare (publish_commands asks for `bot`).
    # Keep check_database the first startup hook: aiogram runs startup hooks before its
    # polling try/finally, so a failing startup hook skips every shutdown hook.
    dispatcher.startup.register(partial(check_database, engine))
    dispatcher.startup.register(partial(check_redis, redis))
    dispatcher.startup.register(partial(publish_commands, session_factory, settings.admin_ids))
    dispatcher.shutdown.register(partial(close_database, engine))
    dispatcher.shutdown.register(partial(close_redis, redis))
    # run_polling handles SIGINT/SIGTERM, swallows KeyboardInterrupt and closes the HTTP
    # session, so Ctrl+C stops the bot cleanly without a traceback.
    dispatcher.run_polling(bot)


if __name__ == "__main__":
    main()
