# 0001. Use Python 3.13 with aiogram 3

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

We need a Telegram bot framework that is async, actively maintained, and fits the audio
pipeline. Audio extraction relies on `yt-dlp`, which is a Python library.

## Decision

Python 3.13 with **aiogram 3.x**, managed with **uv**. Quality gates: ruff, mypy strict,
pytest.

## Alternatives considered

- **TypeScript + grammY** - one language with a future web frontend, but `yt-dlp` would
  run as a subprocess and we'd lose typed, in-process control over extraction.
- **python-telegram-bot** - mature, but aiogram's routers, middlewares, FSM and
  `CallbackData` factories map more cleanly onto our layered design.
- **Pyrogram/Telethon (MTProto)** - not needed; the Bot API covers our features.

## Consequences

- `yt-dlp` is used as a library (no subprocess parsing).
- `yt-dlp` is synchronous, so calls must go through `asyncio.to_thread` with a limit.
- The future Mini App backend (FastAPI) stays in Python and reuses `core/`.
