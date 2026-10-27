---
name: docker-quirks
description: Dockerfile facts verified for this repo: uv_build needs README.md and LICENSE, image size, safe container checks
metadata:
  type: project
---

- `uv sync --locked --no-dev` builds the project, and pyproject's `readme`/`license-files`
  make uv_build need `README.md` and `LICENSE` in the build stage (not in `.dockerignore`).
- The project installs editable: the venv points at `/app/src`, so the runtime stage must
  copy `src/` to the same path as the build stage (`/app`).
- Image is ~704MB, mostly Debian's ffmpeg dependency tree (venv is 136MB).
- Safe live check without starting the bot: `docker run --network <proj>_default -e
  BOT_TOKEN=x -e DATABASE_URL=...@db:5432/... --entrypoint alembic <image> current`.
- Host dev DB is published on 5433 here; `docker compose config -q` validates without printing `.env`.
