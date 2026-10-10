# 0004. Use PostgreSQL for persistence and Redis for caching

- **Status:** Proposed
- **Date:** 2026-10-06

## Context

We persist users, invites and a track → Telegram `file_id` cache, and later profiles,
favourites and history. We also need short-lived caches (search results, profile
listings), rate limiting and aiogram FSM storage that survive restarts.

## Decision

- **PostgreSQL** via SQLAlchemy 2 (async, `asyncpg`), schema migrations with **Alembic**.
- **Redis** for caches, throttling and aiogram FSM storage.
- Both run in Docker Compose locally and in production.

## Alternatives considered

- **SQLite** - simpler, but diverges from production and handles concurrent writes worse;
  Postgres is also the learning goal.
- **MongoDB** - our data is relational (users ↔ invites ↔ tracks).
- **No Redis (in-memory caches)** - lost on restart; doesn't scale past one process.

## Consequences

- Two services to run and back up; Compose keeps local setup to one command.
- Every schema change ships with an Alembic migration in the same PR.
