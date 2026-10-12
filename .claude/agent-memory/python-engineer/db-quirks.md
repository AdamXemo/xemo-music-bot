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
- `migrations/env.py` calls `get_settings()` only when no `sqlalchemy.url` is set; that needs
  BOT_TOKEN in env or `.env` for `alembic upgrade head`.
