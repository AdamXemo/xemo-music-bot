---
name: aiogram-quirks
description: Verified aiogram 3.31 facts - pydantic pin, router attach-once, run_polling shutdown, fake session for handler tests
metadata:
  type: reference
---

Verified on aiogram 3.31.0 (Bot API 10.3), 2026-10-10:

- aiogram 3.31.0 pins `pydantic<2.14`; `uv add aiogram` downgraded pydantic 2.14.0 -> 2.13.5.
  Expect Dependabot pydantic bumps to be blocked until aiogram relaxes the pin.
- A `Router` can be attached to only one parent (`RuntimeError: Router is already attached`).
  Module-level routers break tests that build a fresh dispatcher per test; the repo uses
  `build_router()` factories in `bot/handlers/*.py` instead.
- `Dispatcher.run_polling(bot)` installs SIGINT/SIGTERM handlers, suppresses
  `KeyboardInterrupt` and closes the bot session; `AiohttpSession` is created lazily, so
  `Bot(...)` can be built outside the event loop.
- Handler tests: `dispatcher.feed_update(bot, Update(...))` with a `BaseSession` subclass
  that records `make_request` calls (see `tests/bot/handlers/test_start.py`). Ruff flags the
  inherited `timeout` params (ASYNC109) and the dummy token (S106); those need commented noqa.
