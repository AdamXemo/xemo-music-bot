"""Process-wide logging configuration."""

import logging

from xemo_music_bot.config import LogLevel

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def setup_logging(level: LogLevel) -> None:
    """Configure the root logger once at startup.

    Args:
        level: Minimum level for log records.
    """
    logging.basicConfig(level=level, format=LOG_FORMAT)
