"""Assembles the aiogram dispatcher from the feature routers."""

from aiogram import Dispatcher

from xemo_music_bot.bot.handlers import start


def build_dispatcher() -> Dispatcher:
    """Create a dispatcher with every feature router attached."""
    dispatcher = Dispatcher()
    dispatcher.include_router(start.build_router())
    return dispatcher
