from sqlalchemy import text

from xemo_music_bot.db.session import create_db_engine, create_session_factory


async def test_session_factory_runs_a_query(database_url: str) -> None:
    engine = create_db_engine(database_url)
    try:
        async with create_session_factory(engine)() as session:
            assert await session.scalar(text("SELECT 1")) == 1
    finally:
        await engine.dispose()
