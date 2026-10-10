# xemo-music-bot

[![CI](https://github.com/AdamXemo/xemo-music-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/AdamXemo/xemo-music-bot/actions/workflows/ci.yml)

A clean, private Telegram music bot: search a track, tap it, listen - inside Telegram,
offline-friendly, no ads, no clutter.

> 🚧 Early development. See the [roadmap](docs/ROADMAP.md).

## Features (planned for v0.1)

- 🔎 Search SoundCloud and get results in a single, tidy message
- 🎧 Receive tracks as Telegram audio (with cover, title, artist) - playable offline
- ⚡ Instant repeat sends via Telegram `file_id` caching
- 🔐 Invite-only access for a small group of friends

## Tech stack

Python 3.13 · aiogram 3 · yt-dlp · PostgreSQL · Redis · Docker · GitHub Actions

## Development

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.13 for you).

```bash
uv sync                          # create .venv and install dependencies
uv run pre-commit install        # run format, lint and type checks on every commit
cp .env.example .env             # then fill in BOT_TOKEN and ADMIN_IDS
uv run python -m xemo_music_bot  # run
```

Checks: `uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest`

## Documentation

- [Roadmap](docs/ROADMAP.md) · [Architecture](docs/ARCHITECTURE.md) ·
  [Decisions (ADRs)](docs/adr/) · [Contributing](CONTRIBUTING.md)

## Disclaimer

This is a personal, non-commercial learning project used by a small private group.
It does not host or distribute audio; content belongs to its respective rights holders.
