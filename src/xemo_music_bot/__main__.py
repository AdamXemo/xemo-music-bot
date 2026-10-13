"""Entrypoint: `python -m xemo_music_bot` or the `xemo-music-bot` script."""

import logging
from functools import partial

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.config import get_settings
from xemo_music_bot.db.session import check_connection, create_db_engine, create_session_factory
from xemo_music_bot.logging_setup import setup_logging

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


def main() -> None:
    """Load settings, configure logging and run the bot with long polling until stopped."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Settings loaded, %d admin(s) configured", len(settings.admin_ids))
    # HTML for every message (MVP spec): custom emoji slots render as <tg-emoji> tags.
    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    engine = create_db_engine(settings.database_url.get_secret_value())
    dispatcher = build_dispatcher(create_session_factory(engine), settings.admin_ids)
    # partial binds the engine; aiogram calls hooks only with the arguments they declare.
    # Keep check_database the first startup hook: aiogram runs startup hooks before its
    # polling try/finally, so a failing startup hook skips every shutdown hook.
    dispatcher.startup.register(partial(check_database, engine))
    dispatcher.shutdown.register(partial(close_database, engine))
    # run_polling handles SIGINT/SIGTERM, swallows KeyboardInterrupt and closes the HTTP
    # session, so Ctrl+C stops the bot cleanly without a traceback.
    dispatcher.run_polling(bot)


if __name__ == "__main__":
    main()
