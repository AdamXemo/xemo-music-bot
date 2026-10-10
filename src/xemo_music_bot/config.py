"""Application settings.

This is the only module that reads environment variables. Values come from the process
environment first and from a local `.env` file second (see `.env.example`).
"""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Typed, validated configuration for the whole application.

    Attributes:
        bot_token: Telegram bot token from BotFather.
        admin_ids: Telegram user IDs with admin rights (invites, bans).
        log_level: Minimum level for log records.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Unrelated variables in the environment or .env must not crash startup.
        extra="ignore",
    )

    # SecretStr keeps the token out of reprs, logs and tracebacks.
    bot_token: SecretStr
    admin_ids: frozenset[int] = frozenset()
    log_level: LogLevel = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the settings, loading and validating them on first call."""
    return Settings()
