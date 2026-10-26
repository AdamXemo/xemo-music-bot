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
│   ├── commands.py      # command menu and bot descriptions: startup hook, per-user chat menu
│   ├── emoji.py         # custom emoji slots (UX guide); empty until the owner picks ids
│   ├── labels.py        # result_label(): track button text within the 32-character budget
│   ├── handlers/        # one router per feature: start, language, search, library, admin; fallback last
│   ├── keyboards/       # inline keyboard builders + CallbackData factories
│   │   └── language.py  # language picker (first run and `/language`)
│   ├── middlewares/     # access control, DB session, throttling
│   │   ├── db_session.py  # DbSessionMiddleware: one session per update, commit after handler
│   │   └── access.py      # AccessMiddleware: private chats only, members and config admins pass
│   └── locales/         # Texts dataclass + en.py, uk.py, ru.py: every user-facing string (ADR 0005)
├── core/
│   ├── models.py        # domain dataclasses: Track, Playlist, Profile, and the `Language` literal
│   ├── metadata.py      # clean performer and title from raw provider metadata
│   └── services/        # search, delivery, access, library
│       ├── access.py    # AccessService: admin / member / blocked / stranger
│       ├── search.py    # SearchService: search, pages, loading marks over search sessions
│       └── language.py  # LanguageService: change and read users' languages
├── assets/
│   └── default_cover.jpg  # thumbnail for tracks without a usable cover (scripts/make_default_cover.py)
├── providers/
│   ├── base.py          # MusicProvider protocol
│   ├── covers.py        # cover image -> Telegram audio thumbnail (Pillow, ADR 0006)
│   ├── soundcloud.py
│   └── youtube.py
└── db/
    ├── models.py        # SQLAlchemy ORM models
    ├── session.py       # engine + session factory, startup connection check
    ├── redis.py         # Redis client factory, startup connection check
    └── repositories/    # one per aggregate: users, invites, tracks, search sessions
        ├── users.py     # UsersRepository
        └── search_sessions.py  # SearchSessionsRepository (Redis)
migrations/              # Alembic
scripts/                 # one-off developer scripts, not part of the bot
tests/                   # mirrors src/ layout
```

## Key flows

### Search
1. User sends text → `search` handler → `SearchService.search(owner_id, query)`; paging
   calls `get_page`.
2. Service asks the provider for 10 results and returns them as `SearchPage`s of 5; the
   search session (query, results, page) lives in Redis for 30 minutes after its last use.
   `main()` builds the service once and the dispatcher passes it to handlers as
   `search_service`.
3. Handler renders **one** message with inline buttons; pagination edits that message.
   Callback data carries only the session id plus a page number or a result index
   (`track:<id>:<index>`, `page:<id>:<page>`); the query and results live in Redis,
   because Telegram limits callback data to 64 bytes. The `search` router is included
   after the command routers (its unknown-command and non-text handlers match anything)
   and before the fallback. Pager arrows at the ends and the counter are buttons with
   `disabled` set, so the row keeps its shape. An expired or foreign session answers with
   the `results_expired` toast and removes the keyboard.

### Delivery (tap a track)
0. The handler claims the track with `SearchService.start_loading` (a loading mark in
   Redis; a second tap gets `already_loading`), answers `too_long` as an alert if
   `DeliveryService.is_too_long`, then redraws the keyboard from the stored state so the
   track's button is a disabled loading button, and runs the `upload_document` chat
   action. `DeliveryService.deliver(track, send)` takes a `send` callback, so `core`
   stays free of aiogram; the handler's callback calls `sendAudio`. A `finally` always
   releases the mark and redraws the keyboard (skipped silently if the message is gone).
   Failures become a new message: `too_large`, `track_unavailable` (Go+) or
   `download_failed` (any other provider or Telegram error).
   Steps 1-2 and 4 below come with the `file_id` cache item; until then every tap
   downloads.
1. `DeliveryService.get_audio(track_ref)` checks `tracks.tg_file_id`.
2. **Hit** → send by `file_id` instantly (no download, no upload).
3. **Miss** → `async with provider.download(track) as audio` (download semaphore, then
   yt-dlp into a temp dir in a thread, converted to MP3; the dir is removed when the block
   exits, however it exits) → `sendAudio` with metadata + cover → store returned `file_id`.
   The provider refuses over-long tracks before downloading (`TooLongError`), files over
   50 MB (`TooLargeError`) and Go+ previews or DRM-locked tracks (`PreviewOnlyError`).
   yt-dlp saves the cover (the artwork, else the uploader's avatar) into the same temp
   dir; `providers/covers.py` turns it into the thumbnail in a thread (square JPEG, at
   most 320 px, under 200 kB). `audio.thumbnail` is always set: a missing or unusable
   cover becomes the bundled default cover, never an error.
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
1. While `users.language_chosen` is false, `/start` sends the language picker in the
   stored language; once it is true, `/start` sends only the welcome.
   `/language` sends the picker at any time.
2. A pick calls `LanguageService.set_language()`, which also sets `language_chosen`, and
   edits the picker in the new language: into the welcome for the first-run picker, or
   into a confirmation after `/language`.
3. Callback data is stateless (`language:<code>:<origin>`, origin `first_run` or
   `command`), so old pickers keep working; an unknown code fails parsing and never
   reaches the database. Taps no handler matches (forged data, buttons from older
   versions) go to the fallback router, included last: answered without text, and the
   message's keyboard is removed.

## Data model (MVP)

| Table     | Purpose                         | Key columns |
|-----------|---------------------------------|-------------|
| `users`   | Telegram users who joined       | `tg_id` BIGINT PK, `username`, `role` (`user` / `blocked`, text + CHECK `ck_users_role_valid`; admin rights come only from config `ADMIN_IDS`), `invited_by` -> `users.tg_id` (ON DELETE SET NULL), `created_at`; `language` (`en` / `uk` / `ru`, text NOT NULL, server default `en`, CHECK `ck_users_language_valid`; set from Telegram's `language_code` when the row is created, changed via the picker or `/language`); `language_chosen` (boolean NOT NULL, server default false; set true by any language pick; while false, `/start` shows the language picker) |
| `invites` | One-time / limited invite codes | `code` PK, `created_by`, `max_uses`, `uses`, `expires_at`, `revoked_at` |
| `tracks`  | Track metadata + Telegram cache | `provider`, `provider_track_id` (unique pair), `title`, `artist`, `duration`, `tg_file_id` |

Redis (cache only; persistence off, every key has a TTL, losing a key shows `results_expired`):

| Key | Purpose | Value, TTL |
|-----|---------|------------|
| `xemo:search:{sid}` | Search session: owner, query, results | JSON with `v`, 30 min, refreshed on every read |
| `xemo:search:{sid}:page` | Page the results message shows | 0-based int, 30 min, refreshed with the session |
| `xemo:search:{sid}:loading:{index}` | Track being downloaded; `SET NX` refuses a double tap | `1`, 10 min fixed |

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
