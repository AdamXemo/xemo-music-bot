# Roadmap

The single source of truth for **what** gets built and in **which order**.
Each checkbox ≈ one PR. Version tags mark the end of a phase.

Status legend: ✅ done · 🚧 in progress · ⏳ next · 💤 later

---

## Phase 0 - Foundations 🚧 → `v0.0.1`

Goal: an empty but production-shaped repo. No features yet.

- [x] Planning docs: AGENTS.md, ROADMAP, ARCHITECTURE, CONTRIBUTING, ADRs 0001-0004
- [x] Repo conventions: PR/issue templates, `.gitignore`, `.editorconfig`, LICENSE
- [x] Agent team: first subagent (`plan-reviewer`) + roster in AGENTS.md
- [x] Git repo + GitHub remote, squash-merge only, auto-delete merged branches
- [x] Coding agent: `python-engineer` implements roadmap items; main session orchestrates
- [x] Project skeleton: `uv` project, `src/xemo_music_bot/` package, `config.py`, logging
- [x] Tooling: ruff, mypy strict, pytest, pre-commit hooks
- [x] CI: GitHub Actions running format check, lint, mypy, tests on every PR;
      `.github/dependabot.yml` (uv + github-actions, weekly) to keep yt-dlp current
- [x] Branch protection on `main`: PR required, CI status check required, applies to admins
- [x] Bot hello-world: `/start` replies, bot runs locally via long polling
- [ ] Docker: `Dockerfile` (with ffmpeg) + `docker-compose.yml` (bot, postgres, redis);
      proves `docker compose up` runs the hello-world bot

## Phase 1 - MVP: search & listen 🚧 → `v0.1.0`

Goal: friends can search SoundCloud and receive tracks as audio messages.

UX is the priority of this phase: the bot must feel polished and calm, in English, Ukrainian
and Russian. Keep everything else as simple as it can be.

- [x] UX interview: `ux-designer` asks the owner how users interact with the bot, then
      writes the MVP spec in `docs/features/` (onboarding, language, search, results,
      delivery, errors): English mockups plus copy in all three languages
- [x] Agent team: create `db-architect` and `qa-reviewer` via `agent-engineer`
- [x] DB layer 1/2: async engine + session factory, Alembic init, `users` model + first
      migration (incl. `invited_by`), Postgres service container in CI
- [x] DB layer 2/2: `UsersRepository`, DB session middleware, repository tests against Postgres
- [x] Access control: `AccessService` + middleware; strangers and `blocked` get the
      "private bot" reply to `/start` and are otherwise ignored; admins are the
      `admin_ids` from config (the only source of admin rights; drop `'admin'` from the
      `users.role` CHECK), and their `users` row is created on their first update;
      private chats only, for everyone
- [x] i18n 1/2: `users.language` + migration (NOT NULL, server default `'en'`, which
      backfills admin rows created before it; new rows get the language from Telegram),
      user's catalog via middleware, `/start` shows the language picker until a pick
      (`users.language_chosen`) and then only the welcome, `/language`
      (testable by the admin before invites exist).
      The `bot/locales/` catalogs (en, uk, ru) per ADR 0005 already landed with the
      hello-world bot
- [x] i18n 2/2: localized command menu per language, chat-scope commands (admins at
      startup, any user on a language pick), bot description and short description per
      language at startup. The menu lists only the commands that exist (`/start`,
      `/language`); `/help`, `/invite`, `/revoke` and `/ban` add their own entries
> Order note (2026-10-15): search comes first. The Invite codes and Revocation items below
> stay where they are but are done after Delivery; until then the owner tests as an admin.

- [x] Invite codes: `invites` table + migration (`code` as PK); `/invite` (admin) generates
      a code and is added to the admin menu; `/start <code>` creates the user with
      `language` from Telegram and shows the language picker, then the welcome; short spec
      for admin replies first
- [ ] Revocation: `/revoke <code>` and `/ban <user>` (admin); `role = 'blocked'` is
      rejected by the access middleware; config admins cannot be banned; adds both to the
      admin menu
- [x] Provider interface (`MusicProvider`) + SoundCloud provider: search
- [x] Redis: client from config, search session cache (results, page and loading set
      under a short id with TTL)
- [x] Search UX: text message → one results message, inline buttons, pagination by edit
- [x] Provider download: `MusicProvider.download()` via yt-dlp in `asyncio.to_thread`
      behind a semaphore, temp dir always cleaned up, max-duration guard (50 MB upload cap)
- [x] Delivery: track button → `DeliveryService` → `sendAudio` with title/artist/cover/duration
- [x] Delivery timings (`LOG_TIMINGS`)
- [ ] Rich cards spike: throwaway script sends a rich-message track list to the owner's
      and friends' devices; decides whether cards replace track buttons later
- [x] `file_id` cache: `tracks` table; repeat requests are instant, no re-download
- [ ] De-duplicate in-flight downloads of the same track
- [ ] Error UX: friendly messages for not found / too long / source failure
- [ ] Draft the hosting ADR (VPS vs home server) so Phase 2 starts right at `v0.1.0`

> Search is **by track name only**; SoundCloud links are only for linking a profile
> (ADR 0002).

## Phase 2 - Deploy for friends 💤 → `v0.2.0`

Goal: the bot runs 24/7 and updates itself on merge.

- [ ] Accept the hosting ADR and provision the host
- [ ] Production compose file, secrets via env, healthcheck
- [ ] CD: GitHub Actions builds image → GHCR → deploys on tag
- [ ] Postgres backups, structured logs, basic error alerting (e.g. to admin chat)
- [ ] Scheduled workflow: SoundCloud search + download smoke test against a known track

## Phase 3 - Friends' requests 💤 → `v0.3.0`

Goal: the features the friend group asked for after the first real test (October 2026).
Each user-facing item gets a `ux-designer` spec first; each new external source gets an ADR.

- [ ] Original covers: look up the official release cover by artist, title and duration
      (candidates: Deezer API, iTunes Search API, MusicBrainz + Cover Art Archive; all free
      and keyless) and use it only on a confident match, else today's chain (SoundCloud
      artwork, uploader avatar, default cover). SoundCloud artwork is often a custom
      uploader image, not the release cover
- [ ] Lyrics: look up a delivered track's lyrics (candidate source: LRCLIB, free and
      keyless, plain and synced lyrics matched by artist, title and duration), cached in
      Redis. The spec decides the entry point: a button under the audio reverses the MVP's
      "no buttons on audio" decision, the alternatives are a command or a reply
- [ ] Albums: search albums as well as tracks, open an album to see its tracks, tap one or
      send all. Builds the bulk sending (progress message, rate limiting) that "send whole
      playlist" reuses; needs the `file_id` cache. A spike first checks what yt-dlp and
      SoundCloud offer for album search
- [ ] Chords spike: no chords site offers an API (Ultimate Guitar and Chordify forbid
      scraping), so compare chord recognition from the audio itself with a link out to a
      chords search; decide in an ADR. Tabs come after chords

## Phase 4 - SoundCloud profiles 💤 → `v0.4.0`

Goal: browse your own public SoundCloud library inside the bot.

- [ ] `/profile` - link a public SoundCloud profile by username or URL
- [ ] Browse likes (paginated) and playlists → tap to receive tracks
- [ ] "Send whole playlist", reusing the bulk sending built for albums (Phase 3)
- [ ] Cache profile listings in Redis with short TTL

## Phase 5 - Quality of life 💤 → `v0.5.0`

- [ ] Inline mode: `@xemo_music_bot query` in any chat
- [ ] YouTube provider behind a feature flag
- [ ] In-bot favourites and recent history
- [ ] Settings screen (absorbs `/language`): per-user settings (default source, audio quality)

## Phase 6 - Mini App 💤 → `v1.0.0`

Goal: a Spotify-like player opened from inside Telegram.

- [ ] ADR: frontend stack + FastAPI backend reusing `core/`
- [ ] Auth via Telegram `initData` validation
- [ ] Player with queue, library, search, playlists
- [ ] Streaming endpoint (no persistent audio storage)

## Ideas backlog (unsorted, not committed)

- Caption on delivered audio linking to the bot, so friends who receive a forwarded track
  can find it
- Shared friend playlists / "what friends are listening to"
- Official SoundCloud OAuth (requires Artist Pro - see ADR 0002)
- Last.fm scrobbling, recommendations
- Quality-of-service dashboard (download latency, cache hit rate)
