---
name: aiogram-disabled-button-chat-action
description: aiogram 3.31 has InlineKeyboardButton.disabled=DisabledButton(); ChatActionSender usage and handler-test notes from Search UX 2/2
metadata:
  type: reference
---

- `InlineKeyboardButton(text=..., disabled=DisabledButton())` exists in aiogram 3.31 (Bot API
  10.3); a disabled button carries no `callback_data`. `DisabledButton` imports from `aiogram.types`.
- `ChatActionSender.typing(chat_id=, bot=)` is an async context manager; its worker sends the
  action at the first loop yield (initial sleep 0), so a handler test sees a `SendChatAction`
  in the recorded requests if the fake provider awaits once (`asyncio.sleep(0)`). Filter
  `SendMessage` when asserting replies.
- `Router` handlers with no filter (`router.message.register(fn)`) catch all remaining
  messages, so the search router must be included after start/language routers.
- Handler tests that need real Redis override the conftest `search_service` fixture locally
  (fake provider + `SearchSessionsRepository(redis)`).
- Locale tests: `results_header` holds `<b>`, so `test_copy_is_valid_html_text` strips it for that field.
- Ruff RUF001 also flags the pager angle quotes and a literal NBSP in tests (use `\N{NO-BREAK SPACE}`).
