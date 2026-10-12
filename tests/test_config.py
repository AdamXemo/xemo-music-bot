from pathlib import Path

import pytest
from pydantic import ValidationError

from xemo_music_bot.config import Settings, get_settings


def test_missing_bot_token_is_rejected() -> None:
    with pytest.raises(ValidationError, match="bot_token"):
        Settings()


def test_defaults_apply_when_only_token_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")

    settings = Settings()

    assert settings.admin_ids == frozenset()
    assert settings.log_level == "INFO"


def test_admin_ids_are_parsed_from_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("ADMIN_IDS", "[1, 2, 2]")

    assert Settings().admin_ids == {1, 2}


def test_invalid_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("LOG_LEVEL", "VERBOSE")

    with pytest.raises(ValidationError, match="log_level"):
        Settings()


def test_bot_token_is_hidden_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "super-secret")

    settings = Settings()

    assert "super-secret" not in repr(settings)
    assert settings.bot_token.get_secret_value() == "super-secret"


def test_settings_are_read_from_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("BOT_TOKEN=from-file\nLOG_LEVEL=DEBUG\n")
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    assert settings.bot_token.get_secret_value() == "from-file"
    assert settings.log_level == "DEBUG"


def test_database_url_defaults_to_local_compose_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")

    assert (
        Settings().database_url.get_secret_value()
        == "postgresql+asyncpg://xemo:xemo@localhost:5432/xemo_music_bot"
    )


def test_database_url_is_read_from_env_and_hidden_in_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "postgresql+asyncpg://bot:s3cret@db:5432/music"
    monkeypatch.setenv("BOT_TOKEN", "token")
    monkeypatch.setenv("DATABASE_URL", url)

    settings = Settings()

    assert settings.database_url.get_secret_value() == url
    assert "s3cret" not in repr(settings)


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_TOKEN", "token")

    assert get_settings() is get_settings()
