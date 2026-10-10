# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, Cursor, …) working in this repo.
Humans: see [README.md](README.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## Project in one paragraph

**xemo-music-bot** is a private Telegram bot for a small group of friends: search a track,
tap it, get it as a Telegram audio message (playable offline). Sources are SoundCloud
(primary) and YouTube (optional), both via `yt-dlp`. Access is allowlist/invite-only.
It is a non-commercial hobby + learning project; the owner reviews every line and merges
every PR personally. A Telegram Mini App (web player) is planned for a later phase.

## Where things live

| Need                              | Read                                       |
|-----------------------------------|--------------------------------------------|
| What to build next, phase status  | [docs/ROADMAP.md](docs/ROADMAP.md)         |
| Layers, data flow, boundaries     | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Why a decision was made           | [docs/adr/](docs/adr/)                     |
| Spec of a feature before building | [docs/features/](docs/features/)           |
| Commits, branches, PRs, style     | [CONTRIBUTING.md](CONTRIBUTING.md)         |

Read `ROADMAP.md` and `ARCHITECTURE.md` before starting any non-trivial task.

## Stack

Python 3.13 · aiogram 3 · yt-dlp + ffmpeg · PostgreSQL (SQLAlchemy 2 async + Alembic) ·
Redis · pydantic-settings · uv · ruff · mypy (strict) · pytest · Docker Compose · GitHub Actions.

## Commands

> Available once Phase 0 (project skeleton) is merged.

```bash
uv sync                      # install deps
uv run ruff format .         # format
uv run ruff check . --fix    # lint
uv run mypy src              # type-check
uv run pytest                # tests
docker compose up -d db redis  # local infra
uv run python -m xemo_music_bot  # run the bot
```

All four checks (format, lint, mypy, pytest) must pass before you call a task done.

## Workflow rules

1. **One task = one branch = one PR.** Pick the next unchecked item in `ROADMAP.md`
   unless told otherwise. Never work directly on `main`.
2. **Keep diffs reviewable.** The owner reads every line. Aim for < ~400 changed lines
   per PR; split larger work into stacked PRs.
3. **Spec first for features.** A user-facing feature gets a short spec in
   `docs/features/` (copy `_template.md`) before code, unless it's trivial.
4. **Decisions get ADRs.** New dependency, new service, schema strategy change, or
   anything that's hard to reverse → add an ADR in `docs/adr/` (copy `0000-template.md`).
   Ask the owner before adding a runtime dependency.
5. **Update the docs you touched.** Tick the ROADMAP checkbox, update ARCHITECTURE if
   boundaries moved, add a line to `CHANGELOG.md` under `Unreleased`.
6. **Commit messages follow Conventional Commits** (see CONTRIBUTING.md). Do not push or
   open PRs unless asked.

## Architecture rules (enforced in review)

- `bot/` (Telegram layer) → `core/` (services) → `providers/`, `db/`. Never the other way.
- `core/` must not import `aiogram`. It will be reused by the future Mini App backend.
- Handlers are thin: parse input → call one service → render via keyboards/texts.
- All user-facing strings live in `bot/texts.py`. No string literals in handlers.
- `yt-dlp` is synchronous - always run it via `asyncio.to_thread` behind a concurrency
  limit. Never block the event loop.
- Every DB access goes through a repository in `db/repositories/`.
- Config comes only from `config.py` (pydantic-settings, env vars). No `os.getenv` elsewhere.

## Code style

- Type hints everywhere; `mypy --strict` clean. Prefer `dataclass(slots=True, frozen=True)`
  for domain objects.
- Google-style docstrings on public modules, classes and functions.
- Comments explain **why**, not what. No commented-out code.
  `TODO`s must reference an issue: `# TODO(#12): ...`.
- Use `logging` via `logging.getLogger(__name__)`; never `print`.
- Small functions, early returns, explicit names over clever ones.

## Agent team

Specialised subagents live in `.claude/agents/` (one markdown file each, committed).
The main session acts as the **software engineer** and delegates focused work to them.
Subagents report back; only the main session edits code unless a role says otherwise.

| Agent            | Role                                                    | Status  |
|------------------|---------------------------------------------------------|---------|
| `plan-reviewer`  | Critiques ROADMAP / ARCHITECTURE / ADRs, proposes fixes | ✅ ready |
| `ux-designer`    | Message flows, keyboards, copy in `texts.py`, Mini App UI | 💤 Phase 1 |
| `db-architect`   | Schema, migrations, indexes, query review               | 💤 Phase 1 |
| `qa-reviewer`    | Reviews diffs for bugs, missing tests, rule violations  | 💤 Phase 1 |
| `brainstormer`   | Feature ideas tailored to the friend group → backlog    | 💤 later |

Add a role only when there's real work for it; tune prompts as we learn what helps.

## Never

- Commit secrets, `.env`, cookies, or downloaded audio.
- Persist audio files beyond the upload to Telegram (temp files are deleted after send).
- Add public-facing features (public channels, open sign-up) - the bot is private by design
  (see ADR 0003).
- Silence a type error or lint rule without a comment explaining why.
- Add AI/tool attribution ("Generated with ...", `Co-Authored-By`) to commits, PRs or
  comments, or use em/en dashes - write a plain `-` (see CONTRIBUTING.md, Writing style).
