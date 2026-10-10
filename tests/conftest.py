from collections.abc import Iterator

import pytest

from xemo_music_bot.config import get_settings

SETTINGS_ENV_VARS = ("BOT_TOKEN", "ADMIN_IDS", "LOG_LEVEL")


@pytest.fixture(autouse=True)
def isolated_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    """Keep tests independent of the developer's shell and local `.env`."""
    for name in SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # Settings reads `.env` relative to the working directory; an empty dir has none.
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
