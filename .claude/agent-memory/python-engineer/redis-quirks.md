---
name: redis-quirks
description: Verified redis-py 8.1 typing and local Redis test setup facts (Redis item, 2026-10-15)
metadata:
  type: reference
---

- redis 8.1.0 ships py.typed with sync/async overloads (`getex`, `mget`, `set`), so
  `await redis.mget(...)` / `await pipe.execute()` need no isinstance narrowing under mypy strict.
  Bare `Redis` (no generic arg) type-checks; `Redis.from_url(url, decode_responses=True)` gives str.
- `redis.asyncio.Redis.pipeline(transaction=True)` is an async context manager; queued
  commands (`pipe.set(...)`) are not awaited, only `await pipe.execute()`.
- Tests: `TEST_REDIS_URL=redis://127.0.0.1:6379/15` (fixture flushes the index); compose
  Redis worked on host port 6379 on the owner laptop (2026-10-15). Postgres test DB is on 5433.
