"""Reads and writes search sessions kept in Redis.

A session holds the query, the results and the page of one search, so callback data can
carry only the session id (Telegram limits it to 64 bytes). Redis is a cache: a missing
session is the normal "expired" outcome, never an error.
"""

import json
import logging
import secrets
from collections.abc import Collection
from dataclasses import asdict
from datetime import timedelta
from typing import Final

from redis.asyncio import Redis

from xemo_music_bot.core.models import SearchSession, Track

logger = logging.getLogger(__name__)

KEY_PREFIX: Final = "xemo:search:"
# Bump when the stored JSON changes shape; older payloads then read as expired.
PAYLOAD_VERSION: Final = 1


def _session_key(session_id: str) -> str:
    return f"{KEY_PREFIX}{session_id}"


def _page_key(session_id: str) -> str:
    return f"{KEY_PREFIX}{session_id}:page"


def _loading_key(session_id: str, index: int) -> str:
    return f"{KEY_PREFIX}{session_id}:loading:{index}"


class SearchSessionsRepository:
    """Search sessions under ``xemo:search:`` in Redis.

    A session lives ``ttl`` after its last read; a loading mark lives a fixed
    ``loading_ttl`` so a crashed download cannot block a track for long.
    """

    def __init__(
        self,
        redis: Redis,
        ttl: timedelta = timedelta(minutes=30),
        loading_ttl: timedelta = timedelta(minutes=10),
    ) -> None:
        self._redis = redis
        self._ttl = ttl
        self._loading_ttl = loading_ttl

    async def create(self, owner_id: int, query: str, tracks: Collection[Track]) -> SearchSession:
        """Store a new session on page 0 under a fresh random id.

        Args:
            owner_id: Telegram ID of the user who searched.
            query: The search text.
            tracks: The results, in display order; must not be empty.

        Raises:
            ValueError: ``tracks`` is empty (there is nothing to page through).
            RuntimeError: A key for the new id already exists, which a random id should
                make practically impossible.
        """
        if not tracks:
            raise ValueError("A search session needs at least one track")
        session = SearchSession(
            id=secrets.token_urlsafe(12),
            owner_id=owner_id,
            query=query,
            tracks=tuple(tracks),
            page=0,
        )
        payload = json.dumps(
            {
                "v": PAYLOAD_VERSION,
                "owner_id": owner_id,
                "query": query,
                "tracks": [asdict(track) for track in session.tracks],
            }
        )
        # One transaction so the session never exists without its page key.
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(_session_key(session.id), payload, ex=self._ttl, nx=True)
            pipe.set(_page_key(session.id), 0, ex=self._ttl, nx=True)
            stored = await pipe.execute()
        if not all(stored):
            raise RuntimeError(f"Search session id collision: {session.id}")
        return session

    async def get(self, session_id: str) -> SearchSession | None:
        """Return the session and extend its life by the TTL, or ``None`` if it is gone.

        A payload that is corrupt or from another version also reads as ``None``.
        """
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.getex(_session_key(session_id), ex=self._ttl)
            pipe.getex(_page_key(session_id), ex=self._ttl)
            payload, page = await pipe.execute()
        if payload is None:
            return None
        try:
            data = json.loads(payload)
            if data["v"] != PAYLOAD_VERSION:
                return None
            return SearchSession(
                id=session_id,
                owner_id=data["owner_id"],
                query=data["query"],
                tracks=tuple(Track(**item) for item in data["tracks"]),
                # A lost page key (it expires with the session) means the first page.
                page=int(page) if page is not None else 0,
            )
        except (ValueError, TypeError, KeyError):
            logger.warning("Dropping corrupt search session %s", session_id)
            return None

    async def set_page(self, session_id: str, page: int) -> bool:
        """Remember the page the results message shows, if the session still exists.

        Returns:
            ``False`` if the session expired; no key is created in that case.
        """
        # XX: a late tap on an expired session must not resurrect a half-empty one.
        stored = await self._redis.set(_page_key(session_id), page, ex=self._ttl, xx=True)
        return bool(stored)

    async def mark_loading(self, session_id: str, index: int) -> bool:
        """Mark a result as being downloaded.

        Returns:
            ``False`` if it is already marked, so the caller can ignore a double tap.
        """
        stored = await self._redis.set(
            _loading_key(session_id, index), "1", ex=self._loading_ttl, nx=True
        )
        return bool(stored)

    async def unmark_loading(self, session_id: str, index: int) -> None:
        """Clear the loading mark of a result; a missing mark is fine."""
        await self._redis.delete(_loading_key(session_id, index))

    async def loading_indices(self, session_id: str, indices: Collection[int]) -> frozenset[int]:
        """Return which of the given result indices are being downloaded, in one round trip."""
        if not indices:
            return frozenset()
        ordered = list(indices)
        marks = await self._redis.mget([_loading_key(session_id, index) for index in ordered])
        return frozenset(index for index, mark in zip(ordered, marks, strict=True) if mark)
