import json
from datetime import timedelta

import pytest
from redis.asyncio import Redis

from xemo_music_bot.core.models import Track
from xemo_music_bot.db.repositories.search_sessions import SearchSessionsRepository

TTL_SECONDS = 30 * 60
LOADING_TTL_SECONDS = 10 * 60

TRACKS = (
    Track("soundcloud", "1", "Song", "Artist", 200, "https://img/1.jpg", "https://sc/1"),
    Track("soundcloud", "2", "Other", "", 90, None, "https://sc/2"),
)


@pytest.fixture
def repository(redis: Redis) -> SearchSessionsRepository:
    return SearchSessionsRepository(redis)


def session_key(session_id: str) -> str:
    return f"xemo:search:{session_id}"


def page_key(session_id: str) -> str:
    return f"xemo:search:{session_id}:page"


async def test_get_returns_what_create_stored(repository: SearchSessionsRepository) -> None:
    created = await repository.create(owner_id=7, query="дафт панк 🎧", tracks=TRACKS)

    loaded = await repository.get(created.id)

    assert loaded == created
    assert loaded is not None
    assert loaded.tracks == TRACKS
    assert loaded.tracks[1].artwork_url is None
    assert (loaded.owner_id, loaded.query, loaded.page) == (7, "дафт панк 🎧", 0)


async def test_create_gives_each_session_its_own_id(repository: SearchSessionsRepository) -> None:
    first = await repository.create(1, "a", TRACKS)
    second = await repository.create(1, "a", TRACKS)

    assert first.id != second.id


async def test_create_rejects_empty_results_and_stores_nothing(
    repository: SearchSessionsRepository, redis: Redis
) -> None:
    with pytest.raises(ValueError, match="at least one track"):
        await repository.create(1, "nothing", ())

    assert await redis.dbsize() == 0


async def test_create_sets_the_ttl_on_both_keys(
    repository: SearchSessionsRepository, redis: Redis
) -> None:
    session = await repository.create(1, "a", TRACKS)

    assert await redis.ttl(session_key(session.id)) == pytest.approx(TTL_SECONDS, abs=5)
    assert await redis.ttl(session_key(session.id) + ":page") == pytest.approx(TTL_SECONDS, abs=5)


async def test_get_restores_the_ttl_of_both_keys(
    repository: SearchSessionsRepository, redis: Redis
) -> None:
    session = await repository.create(1, "a", TRACKS)
    await redis.expire(session_key(session.id), 5)
    await redis.expire(session_key(session.id) + ":page", 5)

    await repository.get(session.id)

    assert await redis.ttl(session_key(session.id)) == pytest.approx(TTL_SECONDS, abs=5)
    assert await redis.ttl(session_key(session.id) + ":page") == pytest.approx(TTL_SECONDS, abs=5)


async def test_ttl_is_configurable(redis: Redis) -> None:
    repository = SearchSessionsRepository(redis, ttl=timedelta(minutes=2))

    session = await repository.create(1, "a", TRACKS)

    assert await redis.ttl(session_key(session.id)) == pytest.approx(120, abs=5)


async def test_get_returns_none_for_an_unknown_session(
    repository: SearchSessionsRepository,
) -> None:
    assert await repository.get("nope") is None


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param("not json", id="not-json"),
        pytest.param("[]", id="not-an-object"),
        pytest.param(json.dumps({"v": 2, "owner_id": 1, "query": "a", "tracks": []}), id="version"),
        pytest.param(json.dumps({"v": 1, "owner_id": 1, "query": "a"}), id="missing-field"),
        pytest.param(json.dumps({"v": 1, "owner_id": 1, "query": "a", "tracks": [{}]}), id="track"),
    ],
)
async def test_get_treats_an_unreadable_payload_as_expired(
    repository: SearchSessionsRepository, redis: Redis, payload: str
) -> None:
    await redis.set(session_key("abc"), payload)

    assert await repository.get("abc") is None


async def test_get_warns_about_a_corrupt_payload(
    repository: SearchSessionsRepository, redis: Redis, caplog: pytest.LogCaptureFixture
) -> None:
    await redis.set(session_key("abc"), "not json")

    assert await repository.get("abc") is None
    assert "abc" in caplog.text


async def test_get_treats_an_unreadable_page_as_expired(
    repository: SearchSessionsRepository, redis: Redis
) -> None:
    session = await repository.create(1, "a", TRACKS)
    await redis.set(page_key(session.id), "x")

    assert await repository.get(session.id) is None


async def test_get_defaults_to_the_first_page_when_the_page_key_is_gone(
    repository: SearchSessionsRepository, redis: Redis
) -> None:
    session = await repository.create(1, "a", TRACKS)
    await repository.set_page(session.id, 1)
    await redis.delete(page_key(session.id))

    loaded = await repository.get(session.id)

    assert loaded is not None
    assert loaded.page == 0


async def test_create_raises_on_an_id_collision(
    repository: SearchSessionsRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("secrets.token_urlsafe", lambda _: "fixed")
    first = await repository.create(1, "a", TRACKS)

    with pytest.raises(RuntimeError, match="collision"):
        await repository.create(2, "b", TRACKS)

    assert await repository.get(first.id) == first


async def test_set_page_is_returned_by_get(repository: SearchSessionsRepository) -> None:
    session = await repository.create(1, "a", TRACKS)

    assert await repository.set_page(session.id, 2) is True

    loaded = await repository.get(session.id)
    assert loaded is not None
    assert loaded.page == 2


async def test_set_page_on_an_expired_session_creates_nothing(
    repository: SearchSessionsRepository, redis: Redis
) -> None:
    assert await repository.set_page("gone", 1) is False

    assert await redis.exists(session_key("gone") + ":page") == 0


async def test_mark_loading_refuses_a_second_mark_until_it_is_cleared(
    repository: SearchSessionsRepository,
) -> None:
    assert await repository.mark_loading("s", 3) is True
    assert await repository.mark_loading("s", 3) is False
    assert await repository.mark_loading("s", 4) is True

    await repository.unmark_loading("s", 3)

    assert await repository.mark_loading("s", 3) is True


async def test_loading_mark_has_a_fixed_ttl(
    repository: SearchSessionsRepository, redis: Redis
) -> None:
    await repository.mark_loading("s", 3)

    assert await redis.ttl(session_key("s") + ":loading:3") == pytest.approx(
        LOADING_TTL_SECONDS, abs=5
    )


async def test_loading_indices_returns_only_marked_results(
    repository: SearchSessionsRepository,
) -> None:
    await repository.mark_loading("s", 1)
    await repository.mark_loading("s", 4)
    await repository.mark_loading("other", 2)

    assert await repository.loading_indices("s", [0, 1, 2, 4]) == {1, 4}


async def test_loading_indices_of_nothing_skips_redis(unreachable_redis: Redis) -> None:
    repository = SearchSessionsRepository(unreachable_redis)

    assert await repository.loading_indices("s", []) == frozenset()
