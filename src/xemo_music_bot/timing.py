"""Opt-in timings of a track delivery, to see where its seconds go (``LOG_TIMINGS``).

A neutral module like ``config.py``: ``bot/``, ``core/`` and ``providers/`` may all import
it, and it imports none of them. A tap is wrapped in ``timed_task`` and its steps in
``stage``, or in ``begin``/``end`` for yt-dlp hooks, whose start and end arrive as
separate calls. Each call is a cheap no-op when timings are off or no task is running.

In a terminal, running tasks are drawn live as trees with a spinner and the seconds so
far; otherwise every stage is logged as a ``▶`` line when it starts and a ``✓`` line when
it ends. Stages are also recorded from yt-dlp's worker thread, so a lock guards them.
"""

import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Final, Literal

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text
from rich.tree import Tree

from xemo_music_bot.config import TimingMode

logger = logging.getLogger(__name__)

# "block" stages show in both modes, "stage" ones only with LOG_TIMINGS=stages.
type Detail = Literal["block", "stage"]

_LEVELS: Final[dict[TimingMode, int]] = {"off": 0, "blocks": 1, "stages": 2}
_DETAILS: Final[dict[Detail, int]] = {"block": 1, "stage": 2}
_SPINNER: Final = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SPINNER_FPS: Final = 10


@dataclass(slots=True, eq=False)
class Stage:
    """One timed step, or a whole task when it is the root of a tree.

    Attributes:
        name: What the step does, e.g. ``resolve``.
        started: Clock reading when it began.
        ended: Clock reading when it ended; ``None`` while it runs.
        note: Progress shown next to a running step, e.g. ``41%``.
        children: Steps that ran inside this one, in start order.
    """

    name: str
    started: float
    ended: float | None = None
    note: str = ""
    children: list["Stage"] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        """Seconds from start to end; 0 while the step still runs."""
        return 0.0 if self.ended is None else self.ended - self.started


@dataclass(slots=True, eq=False)
class _Task:
    root: Stage
    # Stages opened by begin(), by name, so end() and update() can find them.
    open: dict[str, Stage] = field(default_factory=dict)


@dataclass(slots=True)
class _Config:
    level: int = 0
    clock: Callable[[], float] = time.perf_counter
    live: Live | None = None


_config = _Config()
_lock = threading.Lock()
_running: list[_Task] = []
_task: ContextVar[_Task | None] = ContextVar("timing_task", default=None)
_parent: ContextVar[Stage | None] = ContextVar("timing_parent", default=None)


def configure(
    mode: TimingMode,
    console: Console | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> Console | None:
    """Set the timing mode; call once at startup, before logging is set up.

    Args:
        mode: ``off``, ``blocks`` or ``stages`` (see the README).
        console: Where the live display draws; stderr by default. Tests pass their own.
        clock: Source of seconds; tests pass a fake one.

    Returns:
        The console of the live display when one started (``console`` is a terminal), so
        logging can print through it above the display; otherwise ``None``.
    """
    close()
    _config.level = _LEVELS[mode]
    _config.clock = clock
    if mode == "off":
        return None
    console = console or Console(stderr=True)
    if not console.is_terminal:
        return None
    _config.live = Live(console=console, refresh_per_second=_SPINNER_FPS, get_renderable=_render)
    _config.live.start()
    return console


def close() -> None:
    """Stop the live display, if any, and give the terminal its cursor back."""
    live, _config.live = _config.live, None
    if live is not None:
        live.stop()


def active() -> bool:
    """Whether a timed task runs in this context, so stages would be recorded."""
    return _task.get() is not None


@contextmanager
def timed_task(title: str) -> Iterator[None]:
    """Time everything inside the block as one task, e.g. one tap on a track.

    Args:
        title: Shown as the root of the task's tree, e.g. ``deliver Artist - Title``.
    """
    if not _config.level:
        yield
        return
    task = _Task(Stage(title, _config.clock()))
    with _lock:
        _running.append(task)
    _log("▶ %s", title)
    task_token, parent_token = _task.set(task), _parent.set(task.root)
    try:
        yield
    finally:
        _parent.reset(parent_token)
        _task.reset(task_token)
        with _lock:
            _end_unfinished(task.root, _config.clock())
            _running.remove(task)
        _print(summarize(task.root))


@contextmanager
def stage(name: str, *, detail: Detail) -> Iterator[None]:
    """Time the block as a step of the current task; stages started inside nest under it.

    Args:
        name: What the step does.
        detail: The least ``LOG_TIMINGS`` mode that shows the step.
    """
    task = _task.get()
    step = None if task is None else _start(task, name, detail)
    if task is None or step is None:
        yield
        return
    token = _parent.set(step)
    try:
        yield
    finally:
        _parent.reset(token)
        _finish(task, step)


def begin(name: str, *, detail: Detail) -> None:
    """Start a step that a later ``end(name)`` finishes; ignored if it already runs.

    Args:
        name: What the step does; ``update`` and ``end`` refer to it by this name.
        detail: The least ``LOG_TIMINGS`` mode that shows the step.
    """
    task = _task.get()
    if task is None or name in task.open:
        return
    step = _start(task, name, detail)
    if step is not None:
        task.open[name] = step


def update(name: str, note: str) -> None:
    """Show ``note`` (e.g. ``41%``) next to a step started with ``begin``, if it runs."""
    task = _task.get()
    step = None if task is None else task.open.get(name)
    if step is not None:
        with _lock:
            step.note = note


def end(name: str) -> None:
    """Finish a step started with ``begin``; does nothing if it is not running."""
    task = _task.get()
    step = None if task is None else task.open.pop(name, None)
    if task is not None and step is not None:
        _finish(task, step)


def summarize(task: Stage) -> list[str]:
    """Describe a finished task in the lines printed (or logged) when it ends.

    Args:
        task: The task's root stage. It and every stage under it (``children``,
            recursively) are finished, so each ``seconds`` is final.

    Returns:
        The total, then every stage depth first, indented by depth, with the slowest
        stage that has no children marked (a block's time already includes theirs).
    """
    stages = list(_walk(task.children, depth=1))
    leaves = [step for step, _ in stages if not step.children]
    slowest = max(leaves, key=lambda step: step.seconds, default=None)
    lines = [f"✓ {task.name} finished in {task.seconds:.1f}s"]
    for step, depth in stages:
        mark = " <- slowest" if step is slowest else ""
        lines.append(f"{'  ' * depth}{step.name} {step.seconds:.1f}s{mark}")
    return lines


def _walk(stages: list[Stage], depth: int) -> Iterator[tuple[Stage, int]]:
    """Yield each stage with its depth, parents before their children."""
    for step in stages:
        yield step, depth
        yield from _walk(step.children, depth + 1)


def _start(task: _Task, name: str, detail: Detail) -> Stage | None:
    """Add a running step under the current parent, or ``None`` if the mode hides it."""
    parent = _parent.get()
    if parent is None or _config.level < _DETAILS[detail]:
        return None
    step = Stage(name, _config.clock())
    with _lock:
        parent.children.append(step)
    _log("▶ %s: %s", task.root.name, name)
    return step


def _finish(task: _Task, step: Stage) -> None:
    # Children begun but never ended (a timeout mid-fetch) end with their parent, so the
    # summary never shows a child outlasting it.
    with _lock:
        _end_unfinished(step, _config.clock())
    _log("✓ %s: %s finished in %.1fs", task.root.name, step.name, step.seconds)


def _end_unfinished(step: Stage, now: float) -> None:
    """End ``step`` and everything under it still running (cancelled, or never ended)."""
    if step.ended is None:
        step.ended = now
    for child in step.children:
        _end_unfinished(child, now)


def _log(message: str, *args: object) -> None:
    """Log a plain line, unless the live display already shows the same thing."""
    if _config.live is None:
        logger.info(message, *args)


def _print(lines: list[str]) -> None:
    # Never under _lock: the live display takes its own lock, then ours in _render.
    live = _config.live
    if live is not None:
        live.refresh()  # drop the finished tree now, not at the next tick
    for line in lines:
        if live is None:
            logger.info("%s", line)
        else:
            live.console.print(Text(line))


def _render() -> Group:
    """Draw every running task as a tree; called by the live display a few times a second."""
    now = _config.clock()
    frame = _SPINNER[int(now * _SPINNER_FPS) % len(_SPINNER)]
    with _lock:
        return Group(*(_tree(task.root, now, frame) for task in _running))


def _tree(step: Stage, now: float, frame: str, parent: Tree | None = None) -> Tree:
    if step.ended is None:
        label = Text(f"{frame} {step.name} {now - step.started:.1f}s {step.note}".rstrip())
    else:
        label = Text(f"✓ {step.name} finished in {step.seconds:.1f}s", style="dim")
    node = Tree(label) if parent is None else parent.add(label)
    for child in step.children:
        _tree(child, now, frame, node)
    return node
