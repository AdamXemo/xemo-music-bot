"""Application settings.

This is the only module that reads environment variables. Values come from the process
environment first and from a local `.env` file second (see the README for the list).
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
        database_url: SQLAlchemy URL of the Postgres database (asyncpg driver).
        redis_url: URL of the Redis cache.
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
    # The default matches the `db` service in docker-compose.yml, so local development
    # needs no extra setup. The URL is secret because it carries the password.
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://xemo:xemo@localhost:5432/xemo_music_bot"
    )
    # 127.0.0.1, not localhost: compose publishes Redis on IPv4 loopback only. Secret
    # because a URL can carry a password.
    redis_url: SecretStr = SecretStr("redis://127.0.0.1:6379/0")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the settings, loading and validating them on first call."""
    return Settings()
