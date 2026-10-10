"""Entrypoint: `python -m xemo_music_bot` or the `xemo-music-bot` script."""

import logging

from aiogram import Bot

from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.config import get_settings
from xemo_music_bot.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Load settings, configure logging and run the bot with long polling until stopped."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Settings loaded, %d admin(s) configured", len(settings.admin_ids))
    bot = Bot(token=settings.bot_token.get_secret_value())
    # run_polling handles SIGINT/SIGTERM, swallows KeyboardInterrupt and closes the HTTP
    # session, so Ctrl+C stops the bot cleanly without a traceback.
    build_dispatcher().run_polling(bot)


if __name__ == "__main__":
    main()
