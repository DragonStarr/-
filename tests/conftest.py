import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import operator_day.db as db_module
from operator_day.config import get_settings
from operator_day.db import get_engine, get_sessionmaker
from operator_day.models import Base


@pytest.fixture(autouse=True)
def reset_runtime_caches():
    get_settings.cache_clear()
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()
    db_module._sqlite_initialized = False
    try:
        yield
    finally:
        get_settings.cache_clear()
        get_sessionmaker.cache_clear()
        get_engine.cache_clear()
        db_module._sqlite_initialized = False


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()
