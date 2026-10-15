from sqlalchemy.ext.asyncio import AsyncEngine

from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.core.services.search import SearchService
from xemo_music_bot.db.session import create_session_factory


def test_dispatcher_passes_the_search_service_to_handlers(
    unreachable_engine: AsyncEngine, search_service: SearchService
) -> None:
    dispatcher = build_dispatcher(
        create_session_factory(unreachable_engine), frozenset(), search_service
    )

    # Workflow data is what aiogram injects into handlers by parameter name.
    assert dispatcher.workflow_data["search_service"] is search_service
