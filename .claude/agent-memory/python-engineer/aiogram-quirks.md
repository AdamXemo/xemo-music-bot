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
- `start_polling` calls `emit_startup` before its try/finally: a failing startup hook skips
  shutdown hooks and bot session close (harmless, the HTTP session is still lazy then).
  `raise SystemExit(1)` in a startup hook exits cleanly with no traceback.
- Hooks/handlers go through `CallableObject`: `functools.partial(async_fn, engine)` is
  detected as awaitable and only declared params get workflow kwargs; a lambda would run
  in a thread and never await. Ruff D102 (not D105) flags a middleware `__call__`.
- Review feedback (2026-10-12, qa-reviewer): "no SendMessage" via feed_update does NOT prove a
  middleware blocked an update - no router may match it anyway. Deny-by-default tests call the
  middleware directly with a handler that records calls, across message / edited_message /
  callback_query, and are checked against a temporary leaky mutation.
- Review feedback (2026-10-12, i18n 1/2a): seed EVERY row's stored language different from the
  Telegram language the tests send (blocked rows too), so each test shows which one a reply used;
  CHANGELOG lines name the roadmap item ("i18n 1/2"), never PR-split jargon like "1/2a".
- CallbackData (3.31): a `Literal`/StrEnum field validates on `unpack`; `CallbackQueryFilter`
  catches TypeError/ValueError (pydantic ValidationError is one), so forged data just matches
  no handler (no answer, no DB write). A field-less subclass packs to the bare prefix.
- `TelegramBadRequest.message` holds Telegram's description ("message is not modified" check).
  To fake an API error, monkeypatch `bot.session.make_request` with `(bot, method, **kwargs)`:
  `BaseSession.__call__` passes `timeout=` by keyword. `feed_update` re-raises handler errors.
- `Message.edit_text(text, inline_message_id, ...)`: pass `reply_markup=` by keyword;
  omitting it removes the inline keyboard.
- `str.split()` on whitespace-only text (e.g. chr(160)) returns `[]`; guard before `[0]`.
- Handler tests: `dispatcher.feed_update(bot, Update(...))` with a `BaseSession` subclass
  that records `make_request` calls (see `tests/bot/handlers/test_start.py`). Ruff flags the
  inherited `timeout` params (ASYNC109) and the dummy token (S106); those need commented noqa.
