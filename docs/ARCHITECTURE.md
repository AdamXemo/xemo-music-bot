# Architecture

How the system is shaped and why. Keep this file in sync when boundaries change.

## Overview

```
 Telegram ──updates──▶ bot/ (aiogram: routers, middlewares, keyboards, locales)
                          │  calls
                          ▼
                       core/ (services + domain models - no aiogram imports)
                       │        │
               ┌───────┘        └────────┐
               ▼                         ▼
        providers/                    db/ (repositories, SQLAlchemy models)
   SoundCloud, YouTube (yt-dlp)          │
                                         ▼
                                  PostgreSQL · Redis
```

**Dependency rule:** arrows point one way only. `core/` knows nothing about Telegram,
so the future Mini App backend (FastAPI) can reuse it unchanged. The one exception:
`providers/` and `db/` may import the plain domain types in `core/models.py`
(dataclasses such as `Track`, which they return and store, and the `Language` literal),
never services.

## Package layout (target)

```
src/xemo_music_bot/
├── __main__.py          # entrypoint: build bot + dispatcher, start polling
├── config.py            # pydantic-settings; the only place env vars are read
├── logging_setup.py     # root logger configuration, called once at startup
├── bot/
│   ├── dispatcher.py    # build_dispatcher(): attaches every feature router
│   ├── emoji.py         # custom emoji slots (UX guide); empty until the owner picks ids
│   ├── handlers/        # one router per feature: start, language, search, library, admin
│   ├── keyboards/       # inline keyboard builders + CallbackData factories
│   │   └── language.py  # welcome's language button, language picker
│   ├── middlewares/     # access control, DB session, throttling
│   │   ├── db_session.py  # DbSessionMiddleware: one session per update, commit after handler
│   │   └── access.py      # AccessMiddleware: private chats only, members and config admins pass
│   └── locales/         # Texts dataclass + en.py, uk.py, ru.py: every user-facing string (ADR 0005)
├── core/
│   ├── models.py        # domain dataclasses: Track, Playlist, Profile, and the `Language` literal
│   ├── metadata.py      # clean performer and title from raw provider metadata
│   └── services/        # search, delivery, access, library
│       ├── access.py    # AccessService: admin / member / blocked / stranger
│       └── language.py  # LanguageService: change a user's language
├── providers/
│   ├── base.py          # MusicProvider protocol
│   ├── soundcloud.py
│   └── youtube.py
└── db/
    ├── models.py        # SQLAlchemy ORM models
    ├── session.py       # engine + session factory, startup connection check
    └── repositories/    # one per aggregate: users, invites, tracks
        └── users.py     # UsersRepository
migrations/              # Alembic
tests/                   # mirrors src/ layout
```

## Key flows

### Search
1. User sends text → `search` handler → `SearchService.search(query, page)`.
2. Service calls the provider (results cached in Redis for a few minutes).
3. Handler renders **one** message with inline buttons; pagination edits that message.
   Callback data carries only `<session_id>:<page>` or `<provider>:<track_id>`; the query
   and results live in Redis, because Telegram limits callback data to 64 bytes.

### Delivery (tap a track)
1. `DeliveryService.get_audio(track_ref)` checks `tracks.tg_file_id`.
2. **Hit** → send by `file_id` instantly (no download, no upload).
3. **Miss** → acquire download semaphore → yt-dlp into a temp dir (in a thread) →
   `sendAudio` with metadata + cover → store returned `file_id` → delete temp file.
4. Concurrent requests for the same track await the same in-flight download.

### Access
`DbSessionMiddleware` (outer, on update) opens one session per update and commits
after the handler; `AccessMiddleware` (outer, on update) runs after it and before every
handler, denying by default:
1. No sender, or a chat that is not private (groups, supergroups, channels): the update
   is dropped before any query, for admins and members too. The bot works in private
   chats only.
2. `AccessService.check()` reads the `users` row. Config admins (`ADMIN_IDS`, the only
   source of admin rights) are admins even with role `blocked` (they cannot be banned),
   and their row is created on their first update.
3. Strangers (no row) and `blocked` users get the "private bot" line in reply to `/start`
   (with or without a payload) and nothing for anything else.
4. Members and admins reach the handlers with `db_user` (their `User` row), `is_admin`
   and `texts` (the catalog for `db_user.language`).

`/start <invite_code>` will be the only way in for friends (Invite codes item).

### Language
1. A pick calls `LanguageService.set_language()` and edits the message in the new
   language: back to the welcome, or to a confirmation after `/language`.
2. Callback data is stateless (`language:<code>:<origin>`), so old pickers keep working;
   an unknown code fails parsing and never reaches the database.

## Data model (MVP)

| Table     | Purpose                         | Key columns |
|-----------|---------------------------------|-------------|
| `users`   | Telegram users who joined       | `tg_id` BIGINT PK, `username`, `role` (`user` / `blocked`, text + CHECK `ck_users_role_valid`; admin rights come only from config `ADMIN_IDS`), `invited_by` -> `users.tg_id` (ON DELETE SET NULL), `created_at`; `language` (`en` / `uk` / `ru`, text NOT NULL, server default `en`, CHECK `ck_users_language_valid`; set from Telegram's `language_code` when the row is created, changed via the picker or `/language`); `language_chosen` (boolean NOT NULL, server default false; set true by any language pick) |
| `invites` | One-time / limited invite codes | `code` PK, `created_by`, `max_uses`, `uses`, `expires_at`, `revoked_at` |
| `tracks`  | Track metadata + Telegram cache | `provider`, `provider_track_id` (unique pair), `title`, `artist`, `duration`, `tg_file_id` |

Later phases add `linked_profiles`, `favorites`, `history`.
Constraint names follow the `MetaData` naming convention in `db/models.py`.

## UX principles

Detailed rules (voice, formal address, premium-emoji-only, typography, glossary) live in
[docs/features/_ux-guide.md](features/_ux-guide.md); the MVP flows in
[docs/features/mvp-search-and-listen.md](features/mvp-search-and-listen.md).

- One message per interaction; update it in place instead of spamming new ones.
- No ads, no forced channel subscriptions, no walls of text.
- Every action gives feedback within ~1s (chat action / "Downloading…" state).
- Errors are short, human, and suggest what to do next.

## Non-goals

- Storing audio files on our side (Telegram holds them via `file_id`).
- Public access, monetisation, or redistribution channels.
