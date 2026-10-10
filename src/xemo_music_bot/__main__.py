"""Entrypoint: `python -m xemo_music_bot` or the `xemo-music-bot` script."""

import logging

from xemo_music_bot.config import get_settings
from xemo_music_bot.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Load settings, configure logging and start the application."""
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Settings loaded, %d admin(s) configured", len(settings.admin_ids))


if __name__ == "__main__":
    main()
