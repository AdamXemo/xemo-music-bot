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
- [ ] Git repo + GitHub remote, branch protection on `main` (PR required, CI must pass)
- [ ] Project skeleton: `uv` project, `src/xemo_music_bot/` package, `config.py`, logging
- [ ] Tooling: ruff, mypy strict, pytest, pre-commit hooks
- [ ] CI: GitHub Actions running format check, lint, mypy, tests on every PR
- [ ] Docker: `Dockerfile` (with ffmpeg) + `docker-compose.yml` (bot, postgres, redis)
- [ ] Bot hello-world: `/start` replies, bot runs locally via long polling

## Phase 1 - MVP: search & listen ⏳ → `v0.1.0`

Goal: friends can search SoundCloud and receive tracks as audio messages.

- [ ] DB layer: SQLAlchemy async engine, Alembic, `users` table, session middleware
- [ ] Access control: allowlist middleware, admin role from config, "private bot" reply
- [ ] Invite codes: `/invite` (admin) generates code, `/start <code>` deep link onboards
- [ ] Provider interface (`MusicProvider`) + SoundCloud provider: search
- [ ] Search UX: text message → one results message, inline buttons, pagination by edit
- [ ] Delivery: download via yt-dlp → `sendAudio` with title/artist/cover/duration
- [ ] `file_id` cache: `tracks` table; repeat requests are instant, no re-download
- [ ] Concurrency: download semaphore + de-duplication of in-flight downloads
- [ ] Error UX: friendly messages for not found / too long / source failure

> Search is **by name only**. SoundCloud links are reserved for linking a profile (Phase 3).

## Phase 2 - Deploy for friends 💤 → `v0.2.0`

Goal: the bot runs 24/7 and updates itself on merge.

- [ ] Choose host (VPS vs home server) - ADR
- [ ] Production compose file, secrets via env, healthcheck
- [ ] CD: GitHub Actions builds image → GHCR → deploys on tag
- [ ] Postgres backups, structured logs, basic error alerting (e.g. to admin chat)

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

- Shared friend playlists / "what friends are listening to"
- Official SoundCloud OAuth (requires Artist Pro - see ADR 0002)
- Lyrics, Last.fm scrobbling, recommendations
- Quality-of-service dashboard (download latency, cache hit rate)
