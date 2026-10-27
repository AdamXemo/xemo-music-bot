# Image for running the bot with `docker compose up -d` (see README, "Run with Docker").
# Two stages: the build stage holds uv and the compilers' leftovers, the runtime stage
# only the finished virtualenv, the source, ffmpeg and a non-root user.

FROM python:3.13-slim AS build

# Pinned to the uv_build range in pyproject.toml (>=0.13.0,<0.14.0).
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

# Precompile bytecode for a faster start; copy (not hardlink) from the cache mount, which
# is not part of the image; use the image's Python instead of downloading another.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so editing code does not reinstall them. pyproject.toml reads
# README.md and LICENSE when it builds the project, hence the second batch.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


FROM python:3.13-slim

RUN apt-get update \
    && apt-get install --no-install-recommends --yes ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 bot

WORKDIR /app

# The project is installed editable, so the venv points at /app/src: keep both here.
COPY --from=build /app/.venv ./.venv
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER bot

# Migrate, then run; `exec` replaces the shell so the bot gets SIGTERM
# from `docker compose down` and shuts down cleanly.
CMD ["sh", "-c", "alembic upgrade head && exec python -m xemo_music_bot"]
