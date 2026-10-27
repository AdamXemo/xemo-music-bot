import logging
from io import StringIO
from typing import Any

import pytest
from rich.console import Console
from rich.logging import RichHandler

from xemo_music_bot.logging_setup import setup_logging


@pytest.fixture
def basic_config_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.append(kwargs))
    return calls


def test_logs_go_to_stderr_without_a_live_display(
    basic_config_calls: list[dict[str, Any]],
) -> None:
    setup_logging("INFO")

    [call] = basic_config_calls
    assert "handlers" not in call


def test_logs_go_through_the_live_display_console(
    basic_config_calls: list[dict[str, Any]],
) -> None:
    console = Console(file=StringIO())

    setup_logging("DEBUG", console)

    [call] = basic_config_calls
    [handler] = call["handlers"]
    assert isinstance(handler, RichHandler)
    assert handler.console is console
    assert call["level"] == "DEBUG"
