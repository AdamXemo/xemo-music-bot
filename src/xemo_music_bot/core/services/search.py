"""Search for tracks and page through the results (feature spec: "Search")."""

from dataclasses import dataclass
from typing import Final

from xemo_music_bot.core.models import SearchSession, Track
from xemo_music_bot.db.repositories.search_sessions import SearchSessionsRepository
from xemo_music_bot.providers.base import MusicProvider

PAGE_SIZE: Final = 5
# Two pages: enough to find a track, and one provider call stays cheap.
RESULT_LIMIT: Final = 10


class SearchSessionExpiredError(Exception):
    """The search session is gone, belongs to someone else, or has no such result.

    One error for all three, so a stale or forged button always gets the same
    ``results_expired`` answer and reveals nothing about other users' searches.
    """


@dataclass(slots=True, frozen=True)
class SearchPage:
    """One page of a search, ready to render.

    Attributes:
        session_id: The session the page belongs to; the part of callback data that
            finds it again.
        query: The search text.
        page: The page shown, counting from 0.
        pages: How many pages the results make; at least 1.
        items: ``(index, track)`` pairs; the index counts across all pages and is what a
            track button carries.
        loading: Indices of results being downloaded, on this page only.
    """

    session_id: str
    query: str
    page: int
    pages: int
    items: tuple[tuple[int, Track], ...]
    loading: frozenset[int]


class SearchService:
    """Finds tracks and keeps the per-message state of the results list in Redis.

    Args:
        provider: The music source to search.
        sessions: Where search sessions are kept.
    """

    def __init__(self, provider: MusicProvider, sessions: SearchSessionsRepository) -> None:
        self._provider = provider
        self._sessions = sessions

    async def search(self, owner_id: int, query: str) -> SearchPage | None:
        """Search the provider and open a session on the first page.

        Args:
            owner_id: Telegram ID of the user who searched.
            query: The search text, already trimmed by the caller.

        Returns:
            The first page, or ``None`` if nothing matched.

        Raises:
            ProviderError: The source failed; the handler shows ``search_failed``.
        """
        tracks = await self._provider.search(query, RESULT_LIMIT)
        if not tracks:
            return None
        session = await self._sessions.create(owner_id, query, tracks)
        # A new session has no loading marks, so skip the lookup.
        return self._render(session, session.page, frozenset())

    async def get_page(self, owner_id: int, session_id: str, page: int) -> SearchPage | None:
        """Turn to a page and remember it as the one the message shows.

        Args:
            owner_id: Telegram ID of the user who tapped.
            session_id: The session id from the callback data.
            page: The wanted page; out-of-range values are clamped to the nearest page.

        Returns:
            The page, or ``None`` if the session expired or belongs to another user.
        """
        session = await self._own_session(owner_id, session_id)
        if session is None:
            return None
        page = self._clamp(page, session)
        if not await self._sessions.set_page(session_id, page):
            return None  # Expired between the read and the write.
        return await self._load_page(session, page)

    async def current_page(self, owner_id: int, session_id: str) -> SearchPage | None:
        """Return the page the message currently shows, for example to restore buttons.

        Returns:
            The page, or ``None`` if the session expired or belongs to another user.
        """
        session = await self._own_session(owner_id, session_id)
        if session is None:
            return None
        return await self._load_page(session, self._clamp(session.page, session))

    async def start_loading(self, owner_id: int, session_id: str, index: int) -> Track | None:
        """Claim a result for download, so a double tap cannot start a second one.

        Args:
            owner_id: Telegram ID of the user who tapped.
            session_id: The session id from the callback data.
            index: The result's index across all pages.

        Returns:
            The track, or ``None`` if it is already loading.

        Raises:
            SearchSessionExpiredError: The session is gone or not the user's, or has no
                result with this index.
        """
        session = await self._own_session(owner_id, session_id)
        if session is None or not 0 <= index < len(session.tracks):
            raise SearchSessionExpiredError(session_id)
        if not await self._sessions.mark_loading(session_id, index):
            return None
        return session.tracks[index]

    async def finish_loading(self, session_id: str, index: int) -> None:
        """Release a result claimed by ``start_loading``, whether it was sent or failed."""
        await self._sessions.unmark_loading(session_id, index)

    async def _own_session(self, owner_id: int, session_id: str) -> SearchSession | None:
        session = await self._sessions.get(session_id)
        if session is None or session.owner_id != owner_id:
            return None
        return session

    def _pages(self, session: SearchSession) -> int:
        return -(-len(session.tracks) // PAGE_SIZE)

    def _clamp(self, page: int, session: SearchSession) -> int:
        return min(max(page, 0), self._pages(session) - 1)

    async def _load_page(self, session: SearchSession, page: int) -> SearchPage:
        first = page * PAGE_SIZE
        indices = range(first, min(first + PAGE_SIZE, len(session.tracks)))
        loading = await self._sessions.loading_indices(session.id, indices)
        return self._render(session, page, loading)

    def _render(self, session: SearchSession, page: int, loading: frozenset[int]) -> SearchPage:
        first = page * PAGE_SIZE
        items = tuple(enumerate(session.tracks[first : first + PAGE_SIZE], start=first))
        return SearchPage(
            session_id=session.id,
            query=session.query,
            page=page,
            pages=self._pages(session),
            items=items,
            loading=loading,
        )
