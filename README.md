# xemo-music-bot

[![CI](https://github.com/AdamXemo/xemo-music-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/AdamXemo/xemo-music-bot/actions/workflows/ci.yml)

A clean, private Telegram music bot: search a track, tap it, listen - inside Telegram,
offline-friendly, no ads, no clutter.

> Early development. See the [roadmap](docs/ROADMAP.md).

## Features (planned for v0.1)

- Search SoundCloud and get results in a single, tidy message
- Receive tracks as Telegram audio (with cover, title, artist) - playable offline
- Instant repeat sends via Telegram `file_id` caching
- Invite-only access for a small group of friends

## Tech stack

Python 3.13 · aiogram 3 · yt-dlp · PostgreSQL · Redis · Docker · GitHub Actions

## Development

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.13 for you).

```bash
uv sync                          # create .venv and install dependencies
uv run pre-commit install        # run format, lint and type checks on every commit
uv run python -m xemo_music_bot  # run
```

Settings come from environment variables or a local `.env` file (gitignored, never
committed):

| Variable       | Required | Meaning                                                         |
|----------------|----------|-----------------------------------------------------------------|
| `BOT_TOKEN`    | yes      | Token from @BotFather                                           |
| `ADMIN_IDS`    | no       | JSON list of admin Telegram user IDs, e.g. `[123456789]`        |
| `LOG_LEVEL`    | no       | `DEBUG`, `INFO` (default), `WARNING`, `ERROR` or `CRITICAL`     |
| `DATABASE_URL` | no       | asyncpg Postgres URL; defaults to the `docker compose` database |

Checks: `uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest`

### Database

```bash
docker compose up -d db          # local Postgres on port 5432 (the DATABASE_URL default)
uv run alembic upgrade head      # apply migrations
uv run alembic revision --autogenerate --rev-id 000N -m "add something"  # new migration
```

Port 5432 already taken? Set `DB_PORT` and a `DATABASE_URL` with the same port in `.env`
(compose reads it too), and use that port in `TEST_DATABASE_URL` below.

Tests in `tests/db/` are skipped unless `TEST_DATABASE_URL` points to a separate,
disposable database (they drop tables, so never use the development one):

```bash
docker compose exec db createdb -U xemo xemo_test
TEST_DATABASE_URL=postgresql+asyncpg://xemo:xemo@localhost:5432/xemo_test uv run pytest
```

## Documentation

- [Roadmap](docs/ROADMAP.md) · [Architecture](docs/ARCHITECTURE.md) ·
  [Decisions (ADRs)](docs/adr/) · [Contributing](CONTRIBUTING.md)

## Disclaimer

This is a personal, non-commercial learning project used by a small private group.
It does not host or distribute audio; content belongs to its respective rights holders.
