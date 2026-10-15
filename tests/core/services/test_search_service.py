import pytest
from redis.asyncio import Redis

from xemo_music_bot.core.models import SearchSession, Track
from xemo_music_bot.core.services.search import SearchService, SearchSessionExpiredError
from xemo_music_bot.db.repositories.search_sessions import SearchSessionsRepository
from xemo_music_bot.providers.base import ProviderError

OWNER = 7
OTHER = 8


def make_tracks(count: int) -> list[Track]:
    return [
        Track("soundcloud", str(n), f"Song {n}", "Artist", 200, None, f"https://sc/{n}")
        for n in range(count)
    ]


class FakeProvider:
    """Returns canned tracks and records what it was asked for."""

    def __init__(self, tracks: list[Track], error: Exception | None = None) -> None:
        self.tracks = tracks
        self.error = error
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, limit: int) -> list[Track]:
        self.calls.append((query, limit))
        if self.error is not None:
            raise self.error
        return self.tracks[:limit]


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider(make_tracks(12))


@pytest.fixture
def sessions(redis: Redis) -> SearchSessionsRepository:
    return SearchSessionsRepository(redis)


async def open_session(service: SearchService) -> str:
    """Search as OWNER and return the new session's id."""
    page = await service.search(OWNER, "daft punk")
    assert page is not None
    return page.session_id


@pytest.fixture
def service(provider: FakeProvider, sessions: SearchSessionsRepository) -> SearchService:
    return SearchService(provider, sessions)


async def test_search_returns_the_first_page_and_stores_the_session(
    service: SearchService, provider: FakeProvider, sessions: SearchSessionsRepository
) -> None:
    page = await service.search(OWNER, "daft punk")

    assert provider.calls == [("daft punk", 10)]
    assert page is not None
    assert (page.query, page.page, page.pages) == ("daft punk", 0, 2)
    assert page.items == tuple((n, provider.tracks[n]) for n in range(5))
    assert page.loading == frozenset()
    session = await sessions.get(page.session_id)
    assert session is not None
    assert (session.owner_id, session.query, session.tracks, session.page) == (
        OWNER,
        "daft punk",
        tuple(provider.tracks[:10]),
        0,
    )


async def test_search_returns_none_and_stores_nothing_when_nothing_matches(
    sessions: SearchSessionsRepository, redis: Redis
) -> None:
    service = SearchService(FakeProvider([]), sessions)

    assert await service.search(OWNER, "zzzz") is None
    assert [key async for key in redis.scan_iter("xemo:search:*")] == []


async def test_search_lets_a_provider_error_through(sessions: SearchSessionsRepository) -> None:
    service = SearchService(FakeProvider([], error=ProviderError("down")), sessions)

    with pytest.raises(ProviderError):
        await service.search(OWNER, "daft punk")


@pytest.mark.parametrize(
    ("found", "pages", "last_indices"),
    [(3, 1, [0, 1, 2]), (7, 2, [5, 6]), (10, 2, [5, 6, 7, 8, 9])],
    ids=["fewer-than-a-page", "partial-last-page", "full-last-page"],
)
async def test_results_are_split_into_pages_of_five(
    sessions: SearchSessionsRepository, found: int, pages: int, last_indices: list[int]
) -> None:
    service = SearchService(FakeProvider(make_tracks(found)), sessions)
    first = await service.search(OWNER, "x")
    assert first is not None

    last = await service.get_page(OWNER, first.session_id, 99)

    assert last is not None
    assert first.pages == last.pages == pages
    assert [index for index, _ in last.items] == last_indices


class VanishingSessions(SearchSessionsRepository):
    """Loses the session right after reading it, as if its TTL ran out in between."""

    async def get(self, session_id: str) -> SearchSession | None:
        session = await super().get(session_id)
        await self._redis.delete(f"xemo:search:{session_id}", f"xemo:search:{session_id}:page")
        return session


async def test_get_page_returns_none_when_the_session_expires_before_the_page_is_stored(
    provider: FakeProvider, redis: Redis
) -> None:
    service = SearchService(provider, VanishingSessions(redis))
    session_id = await open_session(service)

    assert await service.get_page(OWNER, session_id, 1) is None
    # The late page write must not bring back a half-empty session.
    assert [key async for key in redis.scan_iter("xemo:search:*")] == []


async def test_get_page_returns_that_page_and_remembers_it(
    service: SearchService, sessions: SearchSessionsRepository
) -> None:
    session_id = await open_session(service)

    page = await service.get_page(OWNER, session_id, 1)

    assert page is not None
    assert (page.page, [index for index, _ in page.items]) == (1, [5, 6, 7, 8, 9])
    stored = await sessions.get(session_id)
    assert stored is not None
    assert stored.page == 1


@pytest.mark.parametrize(("asked", "shown"), [(-3, 0), (2, 1), (99, 1)])
async def test_get_page_clamps_to_the_existing_pages(
    service: SearchService, sessions: SearchSessionsRepository, asked: int, shown: int
) -> None:
    session_id = await open_session(service)

    page = await service.get_page(OWNER, session_id, asked)

    assert page is not None
    assert page.page == shown
    stored = await sessions.get(session_id)
    assert stored is not None
    assert stored.page == shown


async def test_get_page_returns_none_for_an_expired_session(service: SearchService) -> None:
    assert await service.get_page(OWNER, "gone", 1) is None


async def test_get_page_treats_another_users_session_as_expired(
    service: SearchService, sessions: SearchSessionsRepository
) -> None:
    session_id = await open_session(service)

    assert await service.get_page(OTHER, session_id, 1) is None
    stored = await sessions.get(session_id)
    assert stored is not None
    assert stored.page == 0


async def test_get_page_marks_only_the_loading_tracks_on_the_shown_page(
    service: SearchService, sessions: SearchSessionsRepository
) -> None:
    session_id = await open_session(service)
    await sessions.mark_loading(session_id, 2)
    await sessions.mark_loading(session_id, 7)

    first = await service.get_page(OWNER, session_id, 0)
    second = await service.get_page(OWNER, session_id, 1)

    assert first is not None
    assert first.loading == frozenset({2})
    assert second is not None
    assert second.loading == frozenset({7})


async def test_current_page_returns_the_page_last_shown(
    service: SearchService, sessions: SearchSessionsRepository
) -> None:
    session_id = await open_session(service)
    await service.get_page(OWNER, session_id, 1)
    await sessions.mark_loading(session_id, 6)

    page = await service.current_page(OWNER, session_id)

    assert page is not None
    assert (page.page, page.loading) == (1, frozenset({6}))
    assert [index for index, _ in page.items] == [5, 6, 7, 8, 9]


async def test_current_page_returns_none_for_expired_or_foreign_sessions(
    service: SearchService, sessions: SearchSessionsRepository
) -> None:
    session_id = await open_session(service)

    assert await service.current_page(OWNER, "gone") is None
    assert await service.current_page(OTHER, session_id) is None


async def test_start_loading_hands_out_the_track_once(
    service: SearchService, sessions: SearchSessionsRepository, provider: FakeProvider
) -> None:
    session_id = await open_session(service)

    first = await service.start_loading(OWNER, session_id, 7)
    second = await service.start_loading(OWNER, session_id, 7)

    assert first == provider.tracks[7]
    assert second is None
    assert await sessions.loading_indices(session_id, [7]) == frozenset({7})


async def test_finish_loading_lets_the_track_load_again(
    service: SearchService, sessions: SearchSessionsRepository, provider: FakeProvider
) -> None:
    session_id = await open_session(service)
    await service.start_loading(OWNER, session_id, 3)

    await service.finish_loading(session_id, 3)

    assert await sessions.loading_indices(session_id, [3]) == frozenset()
    assert await service.start_loading(OWNER, session_id, 3) == provider.tracks[3]


@pytest.mark.parametrize("index", [-1, 10, 999])
async def test_start_loading_rejects_an_index_outside_the_results(
    service: SearchService, sessions: SearchSessionsRepository, index: int
) -> None:
    session_id = await open_session(service)

    with pytest.raises(SearchSessionExpiredError):
        await service.start_loading(OWNER, session_id, index)


async def test_start_loading_raises_for_expired_and_foreign_sessions_without_marking(
    service: SearchService, sessions: SearchSessionsRepository
) -> None:
    session_id = await open_session(service)

    with pytest.raises(SearchSessionExpiredError):
        await service.start_loading(OWNER, "gone", 0)
    with pytest.raises(SearchSessionExpiredError):
        await service.start_loading(OTHER, session_id, 0)

    assert await sessions.loading_indices(session_id, [0]) == frozenset()
