"""Assembles the aiogram dispatcher from the middlewares and feature routers."""

from aiogram import Dispatcher
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from xemo_music_bot.bot.handlers import language, start
from xemo_music_bot.bot.middlewares.access import AccessMiddleware
from xemo_music_bot.bot.middlewares.db_session import DbSessionMiddleware


def build_dispatcher(
    session_factory: async_sessionmaker[AsyncSession], admin_ids: frozenset[int]
) -> Dispatcher:
    """Create a dispatcher with the middlewares and every feature router attached.

    Args:
        session_factory: Opens the per-update database session handlers get as ``session``.
        admin_ids: Telegram IDs from config with admin rights.
    """
    dispatcher = Dispatcher()
    # Outer middleware on update: the session exists before any filter runs, and the
    # access middleware (registered after this one) can read it.
    dispatcher.update.outer_middleware(DbSessionMiddleware(session_factory))
    dispatcher.update.outer_middleware(AccessMiddleware(admin_ids))
    dispatcher.include_router(start.build_router())
    dispatcher.include_router(language.build_router())
    return dispatcher
