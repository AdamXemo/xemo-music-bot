"""Process-wide logging configuration."""

import logging

from rich.console import Console
from rich.logging import RichHandler

from xemo_music_bot.config import LogLevel

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def setup_logging(level: LogLevel, console: Console | None = None) -> None:
    """Configure the root logger once at startup.

    Args:
        level: Minimum level for log records.
        console: The console of the live timings display (``timing.configure``). Records
            then go through it, so they print above the display instead of breaking it.
    """
    if console is None:
        logging.basicConfig(level=level, format=LOG_FORMAT)
        return
    # RichHandler draws its own time and level columns.
    handler = RichHandler(console=console)
    logging.basicConfig(level=level, format="%(name)s: %(message)s", handlers=[handler])
