---
name: rich-quirks
description: Verified rich 15.0 Live/RichHandler facts (timings item, 2026-10-26) - lock order, stale frame, spinner, typing
metadata:
  type: reference
---

Verified on rich 15.0.0 (ships py.typed), 2026-10-26, `src/xemo_music_bot/timing.py`:

- `Live(get_renderable=fn)` calls `fn` from its daemon `_RefreshThread` while holding
  `live._lock`; `console.print` during a Live also takes `live._lock`. So never call the
  console or Live while holding your own lock that `fn` takes (deadlock by lock order).
- `console.print` during a Live redraws the LAST rendered frame, not a fresh `fn()`; call
  `live.refresh()` first to drop a finished tree immediately.
- `Live.start()` hides the cursor, `stop()` restores it: stop it in a `finally` at shutdown.
- A fresh `rich.spinner.Spinner` per refresh always shows frame 0 (start_time is set on first
  render); pick braille frames from the clock instead.
- Test consoles: `Console(file=StringIO(), force_terminal=False)` for plain mode,
  `force_terminal=True` for live; keep the StringIO in a variable (`Console.file` is `IO[str]`,
  mypy rejects `.getvalue()`).
- Python 3.13 dataclass self-reference needs the quoted `list["Stage"]` (F821 / NameError).
- `loop.run_in_executor` does not copy contextvars (to_thread does): pass
  `contextvars.copy_context().run, fn`.
- Review feedback (qa-reviewer, 2026-10-26): anything a yt-dlp hook raises other than
  `DownloadCancelled` fails the download, so instrumentation in hooks is gated
  (`timing.active()`) and wrapped in `except Exception` + warning. Also: put shutdown
  cleanup in a `finally` around ALL of startup (a bad token raises before polling).
- yt-dlp postprocessor hook `postprocessor` key is `pp_key()`: class name minus `PP`, minus a
  leading `FFmpeg` (`ExtractAudio`, `MoveFilesAfterDownload`).
