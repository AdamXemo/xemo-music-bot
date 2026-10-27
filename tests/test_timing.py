import logging
from collections.abc import Iterator
from io import StringIO

import pytest
from rich.console import Console

from xemo_music_bot import timing


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def timings_off_afterwards() -> Iterator[None]:
    yield
    timing.configure("off")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def plain_console() -> Console:
    return Console(file=StringIO(), force_terminal=False)


def logged(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == "xemo_music_bot.timing"]


def run_a_tap(clock: FakeClock) -> None:
    with timing.timed_task("deliver Artist - Title"):
        with timing.stage("download", detail="block"):
            with timing.stage("resolve", detail="stage"):
                clock.now += 1.5
            timing.begin("fetch audio", detail="stage")
            clock.now += 2.4
            timing.end("fetch audio")
        clock.now += 0.1


def test_off_records_nothing(clock: FakeClock, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    assert timing.configure("off", plain_console(), clock) is None

    run_a_tap(clock)

    assert logged(caplog) == []


def test_blocks_mode_logs_only_blocks_and_the_task(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    timing.configure("blocks", plain_console(), clock)

    run_a_tap(clock)

    assert logged(caplog)[:3] == [
        "▶ deliver Artist - Title",
        "▶ deliver Artist - Title: download",
        "✓ deliver Artist - Title: download finished in 3.9s",
    ]
    assert "resolve" not in caplog.text
    assert "fetch audio" not in caplog.text


def test_stages_mode_logs_every_stage_with_its_duration(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    timing.configure("stages", plain_console(), clock)

    run_a_tap(clock)

    assert logged(caplog) == [
        "▶ deliver Artist - Title",
        "▶ deliver Artist - Title: download",
        "▶ deliver Artist - Title: resolve",
        "✓ deliver Artist - Title: resolve finished in 1.5s",
        "▶ deliver Artist - Title: fetch audio",
        "✓ deliver Artist - Title: fetch audio finished in 2.4s",
        "✓ deliver Artist - Title: download finished in 3.9s",
        # The summary when the tap ends:
        "✓ deliver Artist - Title finished in 4.0s",
        "  download 3.9s",
        "    resolve 1.5s",
        "    fetch audio 2.4s <- slowest",
    ]


def test_summary_marks_the_slowest_stage_without_children() -> None:
    # A block (download) always takes longer than its own stages, so only leaves compete.
    task = timing.Stage("tap", 0.0, 10.0)
    download = timing.Stage("download", 1.0, 7.0)
    download.children = [timing.Stage("resolve", 1.0, 2.0), timing.Stage("fetch", 2.0, 5.0)]
    task.children = [timing.Stage("buttons", 0.0, 1.0), download, timing.Stage("upload", 7, 10.5)]

    assert timing.summarize(task) == [
        "✓ tap finished in 10.0s",
        "  buttons 1.0s",
        "  download 6.0s",
        "    resolve 1.0s",
        "    fetch 3.0s",
        "  upload 3.5s <- slowest",
    ]


def test_summary_of_a_task_without_stages_is_the_total_only() -> None:
    assert timing.summarize(timing.Stage("tap", 0.0, 1.0)) == ["✓ tap finished in 1.0s"]


def test_begin_twice_keeps_the_first_start_and_end_twice_is_ignored(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    timing.configure("stages", plain_console(), clock)

    with timing.timed_task("tap"):
        timing.begin("fetch audio", detail="stage")
        clock.now += 1
        timing.begin("fetch audio", detail="stage")  # yt-dlp reports progress many times
        clock.now += 1
        timing.end("fetch audio")
        timing.end("fetch audio")

    assert logged(caplog).count("✓ tap: fetch audio finished in 2.0s") == 1
    assert logged(caplog).count("▶ tap: fetch audio") == 1


def test_stages_outside_a_task_are_not_recorded(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    timing.configure("stages", plain_console(), clock)

    with timing.stage("resolve", detail="stage"):
        timing.begin("fetch audio", detail="stage")
        timing.update("fetch audio", "41%")
        timing.end("fetch audio")

    assert logged(caplog) == []


def test_live_mode_draws_running_stages_and_prints_the_summary_at_the_end(
    clock: FakeClock,
) -> None:
    printed = StringIO()
    console = Console(file=printed, force_terminal=True, width=80)
    assert timing.configure("stages", console, clock) is console
    out = StringIO()
    screen = Console(file=out, width=80)

    with timing.timed_task("tap"):
        with timing.stage("resolve", detail="stage"):
            clock.now += 1
        timing.begin("fetch audio", detail="stage")
        timing.update("fetch audio", "41%")
        clock.now += 2
        screen.print(timing._render())

    drawn = out.getvalue()
    assert "✓ resolve finished in 1.0s" in drawn
    assert "fetch audio 2.0s 41%" in drawn
    assert "tap 3.0s" in drawn
    assert "tap finished in 3.0s" in printed.getvalue()
    # A finished task leaves the live display.
    assert timing._render().renderables == []


def test_a_stage_left_open_ends_with_its_parent(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    timing.configure("stages", plain_console(), clock)

    with timing.timed_task("tap"):
        with timing.stage("download", detail="block"):
            timing.begin("fetch audio", detail="stage")  # e.g. the download timed out
            clock.now += 30
        clock.now += 3

    assert logged(caplog)[-3:] == [
        "✓ tap finished in 33.0s",
        "  download 30.0s",
        "    fetch audio 30.0s <- slowest",
    ]


def test_an_unfinished_stage_ends_with_its_task(
    clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    timing.configure("stages", plain_console(), clock)

    with timing.timed_task("tap"):
        timing.begin("fetch audio", detail="stage")  # e.g. the download was cancelled
        clock.now += 2

    assert logged(caplog)[-2:] == ["✓ tap finished in 2.0s", "  fetch audio 2.0s <- slowest"]
