# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- Search UX 1/2: `SearchService` (search, paging, loading marks over the Redis session),
  the track button label (`result_label`, 32-character budget) and the service wired into
  the dispatcher; no visible change yet.
- Redis: client from `REDIS_URL`, startup connection check, `redis` service in compose and
  CI, and `SearchSessionsRepository` for search sessions (results, page, loading marks).
- Project planning docs: AGENTS.md, roadmap, architecture, contributing guide, ADRs 0001-0004.
- Repo conventions: PR and issue templates, `.gitignore`, `.editorconfig`, MIT license.
- `plan-reviewer` subagent and agent team roster.
- `agent-engineer` subagent for designing and auditing the other agents.
- Project skeleton: `uv` package on Python 3.13, typed settings via pydantic-settings,
  logging setup, `python -m xemo_music_bot` entrypoint; settings documented in the README.
- Tooling: ruff (format + lint), mypy strict with the pydantic plugin, pytest with
  asyncio and coverage, pre-commit hooks; first tests for settings.
- `python-engineer` subagent for implementing roadmap items; the main session becomes
  the orchestrator that delegates and owns git and PRs.
- `ux-designer` subagent with an interview-first workflow.
- CI: GitHub Actions runs format check, lint, mypy and tests on every PR and push to
  `main`; Dependabot opens weekly update PRs for uv packages and actions.
- Branch protection on `main`: PR and green CI required, linear history, applies to admins.
- ADR 0005 (accepted): English, Ukrainian and Russian via typed in-code catalogs.
- `qa-reviewer` (read-only review of python-engineer's changes) and `db-architect`
  (schema, migration and Redis key design and review) subagents.
- Hello-world bot: aiogram long polling via `python -m xemo_music_bot`, `/start` greeting
  in English, Ukrainian or Russian picked from the Telegram language (English fallback).
- MVP UX spec and UX guide (approved) from the owner interview: flows, mockups and copy in
  English, Ukrainian and Russian.
- `MusicProvider` interface and SoundCloud search via yt-dlp (metadata only, off the event
  loop, concurrency-capped), with performer and title cleaned per the MVP spec.
- Database layer 1/2: async SQLAlchemy engine and session factory, `users` model, Alembic
  with the first migration, a local Postgres in `docker-compose.yml` and a Postgres
  service in CI for the database tests.
- Database layer 2/2: `UsersRepository`, a middleware that opens one database session per
  update and commits after the handler, and a startup check that stops the bot with a clear
  log line when Postgres is unreachable; repository tests run against Postgres.
- Access control: only members and config admins reach the bot, in private chats only;
  strangers and blocked users get a "private bot" line on `/start` and are otherwise
  ignored; a config admin's `users` row is created on their first update. Migration 0002
  drops `admin` from the `users.role` CHECK, since admin rights come only from config.
- i18n 1/2: each user's language is stored in `users.language` (migration 0003; existing
  rows get English), taken from Telegram's language when the row is created; handlers get
  the user's catalog from the access middleware, so `/start` greets in the stored language.
- `users.language_chosen` (migration 0004; existing rows get false) records whether a user
  has picked a language; any pick sets it.
- i18n 1/2: until a user picks a language, `/start` sends a language picker (flag and
  name per language) and a pick turns it into the welcome in that language; later
  `/start`s send only the welcome. `/language` sends the picker as a new message and a
  pick turns it into a confirmation. Messages use HTML parse mode.
  Button taps from strangers, blocked users and groups are answered silently; taps on
  buttons no handler recognises are answered silently and those buttons are removed.
- i18n 2/2: at startup the bot publishes its command menu (`/start`, `/language`), description
  and short description in English, Ukrainian and Russian (English for other clients), and
  each config admin's chat menu in their stored language; every language pick also sets that
  user's chat menu, so the menu follows the bot language. Telegram errors there are only
  logged. Menu entries for `/help`, `/invite`, `/revoke` and `/ban` come with their own items.

### Changed
- `plan-reviewer` subagent: settled decisions sourced from Accepted ADRs only, severity labels (must fix / should fix / consider), evidence-based stale-doc and plan-vs-code drift checks, and rules for verifying external facts.
- Roadmap reworked after plan review: branch protection after CI, Redis before search UX,
  DB layer and delivery split into reviewable PRs, revocation, Dependabot and smoke tests.
- ADRs 0001-0004 accepted; ADR 0002 records search-by-name-only and the Deno need for YouTube.
- Phase 1 reordered: access control (config admins get a row on their first update),
  then i18n in two PRs, then invite codes and revocation. Admin rights come from config
  only and config admins cannot be banned (ADR 0003 clarified); ADR 0005 sets the language
  on joining. Redis item drops aiogram `RedisStorage` (no FSM in the MVP spec).
