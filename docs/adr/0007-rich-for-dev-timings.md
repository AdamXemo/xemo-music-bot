# 0007. Draw developer timings with rich

- **Status:** Accepted
- **Date:** 2026-10-26

## Context

A tap on a track takes 10-15 s before the audio arrives. Before speeding anything up, the
owner wants to see where that time goes: a switchable mode (`LOG_TIMINGS`) that shows the
running step with a spinner and its seconds so far, and how long each step took once the
tap is done. Taps can overlap and some steps are reported from yt-dlp's worker thread, so
the display has to redraw several lines in place while normal log lines keep printing.

## Decision

- Add **rich** as a runtime dependency (owner approved, 2026-10-26), used only for the
  developer timings in `timing.py` and, while its live display runs, for log output
  (`RichHandler`, so log lines print above the display instead of breaking it).
- The live display is used only when stderr is a terminal. Elsewhere (Docker logs) the
  same timings are plain log lines, so rich is not needed to read them.
- Off by default; nothing user-facing depends on rich.

## Alternatives considered

- **Hand-written ANSI codes** - no dependency, but redrawing several trees in place,
  keeping log lines above them and handling terminal width is what rich already does well.
- **Plain log lines only** - enough for Docker, but no live view of a step that is still
  running, which is what the owner asked for.
- **A profiler (py-spy, cProfile)** - shows where CPU goes, not wall time spent waiting
  on SoundCloud, yt-dlp, ffmpeg and Telegram, which is the question here.

## Consequences

- One more pure-Python dependency (with markdown-it-py and mdurl); Dependabot keeps it
  current.
- Any code may call `timing.stage(...)` cheaply: with `LOG_TIMINGS=off` it does nothing.
- Using rich anywhere else (user-facing output, other tools) needs its own decision.
