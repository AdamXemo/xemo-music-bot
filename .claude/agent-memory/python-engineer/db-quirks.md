---
name: db-quirks
description: Verified SQLAlchemy 2.1 / Alembic 1.20 / Postgres 18 facts and local DB test setup gotchas (port 5432 taken on owner laptop)
metadata:
  type: reference
---

Verified 2026-10-12 (sqlalchemy 2.1.4, alembic 1.20.0, asyncpg 0.32.0, postgres:18-alpine):

- Owner laptop runs a host Postgres on 127.0.0.1:5432. Start the compose DB with
  `DB_PORT=55432 docker compose up -d db` (compose maps `127.0.0.1:${DB_PORT:-5432}`)
  and point DATABASE_URL / TEST_DATABASE_URL at 55432. `compare_server_default=True` is green on PG18.
- Postgres 18 images mount the volume at `/var/lib/postgresql` (PGDATA is `18/docker`
  under it); mounting `/var/lib/postgresql/data` like 17 breaks.
- `alembic init -t async` in 1.20 already writes `script_location = %(here)s/migrations`;
  its mako template uses `Union[...]`, which ruff UP rewrites, so the repo template is modernised.
- `alembic check` (drift test) does NOT compare CHECK constraints; column type/nullability
  changes are caught. Verify constraints by repository tests instead.
- A second `conftest.py` (tests/db/) makes mypy fail with "Duplicate module named conftest";
  fixed with `mypy_path = "src"` + `explicit_package_bases = true` (no `__init__.py` in tests).
  This also lets mypy check `migrations/versions/0001_*.py` despite the digit-leading name.
- 2026-10-12: owner's compose db may run on 127.0.0.1:5433 with a `xemo_test` database;
  use `TEST_DATABASE_URL=postgresql+asyncpg://xemo:xemo@127.0.0.1:5433/xemo_test`.
- DB fixtures (`database_url`, `migrated_url`, `engine`, `connection`, `session`,
  `unreachable_engine`) live in the ROOT tests/conftest.py so tests/bot/ can use them.
- Unreachable asyncpg raises raw `OSError` (not wrapped); bad password raises
  `sqlalchemy.exc.DBAPIError`. Neither message contains the URL or password.
- `postgresql.insert(User)...on_conflict_do_nothing(...).returning(User)` via
  `session.scalar` is mypy-clean and returns `User | None`.
- `insert(Model).values([{...}, {...}])` takes its columns from the FIRST dict and silently
  drops extra keys of later rows (a `role="blocked"` on row 2 was lost); give every row the same keys.
- `update(User).where(...).values(...).returning(User)` via `session.scalars(...).one_or_none()`
  (default synchronize_session) DOES update an object already in the identity map; verified
  by mutation (`synchronize_session=False` makes the refresh test fail).
- Render offline SQL without touching `.env`: run from the scratchpad with
  `BOT_TOKEN=123456:TEST DATABASE_URL=<test url> uv run --project <repo> alembic -c <repo>/alembic.ini upgrade A:B --sql`.
- Migration data tests: sync test + `asyncio.run` on a throwaway `create_db_engine` with raw
  `text()` SQL (the ORM model is ahead of older revisions); finally-clean rows and upgrade head.
- 2026-10-15: model `mapped_column(server_default=false())` matches migration
  `server_default=sa.false()` under `compare_server_default=True`; a model `"true"` is caught
  by the drift test (`modify_default`), so default mismatches do not slip through.
- `migrations/env.py` calls `get_settings()` only when no `sqlalchemy.url` is set; that needs
  BOT_TOKEN in env or `.env` for `alembic upgrade head`.
