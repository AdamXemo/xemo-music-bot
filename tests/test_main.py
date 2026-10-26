import logging

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from xemo_music_bot import __main__ as entrypoint
from xemo_music_bot import timing
from xemo_music_bot.__main__ import check_database, check_redis, main


def test_timings_display_is_closed_when_startup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "malformed")
    closed: list[None] = []
    monkeypatch.setattr(timing, "configure", lambda _mode: None)
    monkeypatch.setattr(timing, "close", lambda: closed.append(None))
    monkeypatch.setattr(entrypoint, "setup_logging", lambda *_args: None)

    def bad_token(**_kwargs: object) -> None:
        raise ValueError("Token is invalid!")

    monkeypatch.setattr(entrypoint, "Bot", bad_token)

    with pytest.raises(ValueError, match="Token is invalid"):
        main()

    assert closed == [None]


async def test_check_database_passes_when_postgres_is_reachable(engine: AsyncEngine) -> None:
    await check_database(engine)


async def test_check_database_exits_with_a_clear_log_when_postgres_is_unreachable(
    unreachable_engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit) as exit_info:
        await check_database(unreachable_engine)

    assert exit_info.value.code == 1
    [record] = caplog.records
    prefix = "Cannot connect to Postgres - is it running and is DATABASE_URL right?"
    assert record.getMessage().startswith(prefix)
    # The driver's cause follows the fixed prefix, so the log says why it failed.
    assert record.getMessage().removeprefix(prefix).strip()
    # The URL carries the password; it must never reach the logs.
    assert "not-logged" not in caplog.text


async def test_check_redis_passes_when_redis_is_reachable(redis: Redis) -> None:
    await check_redis(redis)


async def test_check_redis_exits_with_a_clear_log_when_redis_is_unreachable(
    unreachable_redis: Redis, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit) as exit_info:
        await check_redis(unreachable_redis)

    assert exit_info.value.code == 1
    [record] = caplog.records
    prefix = "Cannot connect to Redis - is it running and is REDIS_URL right?"
    assert record.getMessage().startswith(prefix)
    # The driver's cause follows the fixed prefix, so the log says why it failed.
    assert record.getMessage().removeprefix(prefix).strip()
    # The URL carries the password; it must never reach the logs.
    assert "not-logged" not in caplog.text
