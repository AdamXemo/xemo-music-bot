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
`providers/` and `db/` may import the plain domain dataclasses in `core/models.py`
(they return and store `Track`), never services.

## Package layout (target)

```
src/xemo_music_bot/
├── __main__.py          # entrypoint: build bot + dispatcher, start polling
├── config.py            # pydantic-settings; the only place env vars are read
├── logging_setup.py     # root logger configuration, called once at startup
├── bot/
│   ├── dispatcher.py    # build_dispatcher(): attaches every feature router
│   ├── handlers/        # one router per feature: start, search, library, admin
│   ├── keyboards/       # inline keyboard builders + CallbackData factories
│   ├── middlewares/     # access control, DB session, throttling
│   │   └── db_session.py  # DbSessionMiddleware: one session per update, commit after handler
│   └── locales/         # Texts dataclass + en.py, uk.py, ru.py: every user-facing string (ADR 0005)
├── core/
│   ├── models.py        # domain dataclasses: Track, Playlist, Profile
│   ├── metadata.py      # clean performer and title from raw provider metadata
│   └── services/        # search, delivery, access, library
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
`AccessMiddleware` runs before every handler: unknown users get a short "private bot"
message; `/start <invite_code>` is the only way in for friends. Admins come from config
(`ADMIN_IDS`), the only source of admin rights, and their `users` row is created on their
first update.
`DbSessionMiddleware` (outer, on update) opens one session per update and commits
after the handler; `AccessMiddleware` runs after it.

## Data model (MVP)

| Table     | Purpose                         | Key columns |
|-----------|---------------------------------|-------------|
| `users`   | Telegram users who joined       | `tg_id` BIGINT PK, `username`, `role` (`user` / `blocked`, text + CHECK; `admin` is in the CHECK until the Access control item drops it, admin rights come from config), `invited_by` -> `users.tg_id` (ON DELETE SET NULL), `created_at`; `language` (`en` / `uk` / `ru`) arrives with the i18n item |
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
