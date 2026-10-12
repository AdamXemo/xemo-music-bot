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
- [ ] DB layer 2/2: `UsersRepository`, DB session middleware, repository tests against Postgres
- [ ] Access control: `AccessService` + middleware; strangers and `blocked` get the
      "private bot" reply to `/start` and are otherwise ignored; admins are the
      `admin_ids` from config (the only source of admin rights; drop `'admin'` from the
      `users.role` CHECK), and their `users` row is created on their first update with
      `language` from Telegram
- [ ] i18n 1/2: `users.language` + migration, user's catalog via middleware, welcome with
      language button, picker, `/language` (testable by the admin before invites exist).
      The `bot/locales/` catalogs (en, uk, ru) per ADR 0005 already landed with the
      hello-world bot
- [ ] i18n 2/2: localized command menu per language, admin chat-scope commands, bot
      description and short description per language at startup
- [x] DB layer 2/2: `UsersRepository`, DB session middleware, repository tests against Postgres
- [ ] i18n: `users.language`, language picked on first `/start` (preselected from
      Telegram), `/language` to switch, localized command menu. The `bot/locales/`
      catalogs (en, uk, ru) per ADR 0005 already landed with the hello-world bot
- [ ] Access control: allowlist middleware, admin role from config, "private bot" reply
- [ ] Invite codes: `invites` table + migration (`code` as PK); `/invite` (admin) generates
      a code; `/start <code>` creates the user with `language` from Telegram and welcomes
      them; short spec for admin replies first
- [ ] Revocation: `/revoke <code>` and `/ban <user>` (admin); `role = 'blocked'` is
      rejected by the access middleware; config admins cannot be banned
- [x] Provider interface (`MusicProvider`) + SoundCloud provider: search
- [ ] Redis: client from config, search session cache (results, page and loading set
      under a short id with TTL)
- [ ] Rich cards spike: throwaway script sends a rich-message track list to the owner's
      and friends' devices; decides whether cards replace track buttons later
- [ ] Search UX: text message → one results message, inline buttons, pagination by edit
- [ ] Provider download: `MusicProvider.download()` via yt-dlp in `asyncio.to_thread`
      behind a semaphore, temp dir always cleaned up, max-duration guard (50 MB upload cap)
- [ ] Delivery: track button → `DeliveryService` → `sendAudio` with title/artist/cover/duration
- [ ] `file_id` cache: `tracks` table; repeat requests are instant, no re-download
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

## Phase 3 - SoundCloud profiles 💤 → `v0.3.0`

Goal: browse your own public SoundCloud library inside the bot.

- [ ] `/profile` - link a public SoundCloud profile by username or URL
- [ ] Browse likes (paginated) and playlists → tap to receive tracks
- [ ] "Send whole playlist" with progress message and rate limiting
- [ ] Cache profile listings in Redis with short TTL

## Phase 4 - Quality of life 💤 → `v0.4.0`

- [ ] Inline mode: `@xemo_music_bot query` in any chat
- [ ] YouTube provider behind a feature flag
- [ ] In-bot favourites and recent history
- [ ] Per-user settings (default source, audio quality)

## Phase 5 - Mini App 💤 → `v1.0.0`

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
- Lyrics, Last.fm scrobbling, recommendations
- Quality-of-service dashboard (download latency, cache hit rate)
