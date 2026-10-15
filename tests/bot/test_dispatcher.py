from sqlalchemy.ext.asyncio import AsyncEngine

from xemo_music_bot.bot.dispatcher import build_dispatcher
from xemo_music_bot.core.services.delivery import DeliveryService
from xemo_music_bot.core.services.search import SearchService
from xemo_music_bot.db.session import create_session_factory


def test_dispatcher_passes_the_services_to_handlers(
    unreachable_engine: AsyncEngine,
    search_service: SearchService,
    delivery_service: DeliveryService,
) -> None:
    dispatcher = build_dispatcher(
        create_session_factory(unreachable_engine), frozenset(), search_service, delivery_service
    )

    # Workflow data is what aiogram injects into handlers by parameter name.
    assert dispatcher.workflow_data["search_service"] is search_service
    assert dispatcher.workflow_data["delivery_service"] is delivery_service
