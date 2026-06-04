from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from operator_day.config import get_settings
from operator_day.domain import TenantContext
from operator_day.models import Base, Sale

_sqlite_initialized = False


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def ensure_local_database() -> None:
    global _sqlite_initialized
    if _sqlite_initialized:
        return
    engine = get_engine()
    if not str(engine.url).startswith("sqlite"):
        _sqlite_initialized = True
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_sqlite_task_columns(conn)
        await _ensure_sqlite_account_columns(conn)
        await _ensure_sqlite_product_columns(conn)
        await _ensure_sqlite_stock_columns(conn)
        await _ensure_sqlite_sales_table(conn)
        await _ensure_sqlite_review_columns(conn)
    _sqlite_initialized = True


async def get_session() -> AsyncIterator[AsyncSession]:
    await ensure_local_database()
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session


async def bind_tenant_scope(
    session,
    ctx: TenantContext,
    *,
    database_url: str | None = None,
) -> None:
    url = database_url or str(get_engine().url)
    if url.startswith("sqlite"):
        return
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": ctx.tenant_id},
    )


async def dispose_engine() -> None:
    await get_engine().dispose()


async def _ensure_sqlite_task_columns(conn: AsyncConnection) -> None:
    result = await conn.execute(text("PRAGMA table_info(tasks)"))
    existing = {row[1] for row in result.fetchall()}
    columns = {
        "score": "FLOAT DEFAULT 0",
        "money_effect": "FLOAT DEFAULT 0",
        "urgency": "FLOAT DEFAULT 0.1",
        "confidence": "FLOAT DEFAULT 0.7",
        "deadline_at": "DATETIME",
    }
    for name, definition in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {definition}"))


async def _ensure_sqlite_account_columns(conn: AsyncConnection) -> None:
    result = await conn.execute(text("PRAGMA table_info(accounts)"))
    existing = {row[1] for row in result.fetchall()}
    columns = {
        "title": "VARCHAR(200) DEFAULT ''",
        "payload": "JSON DEFAULT '{}'",
    }
    for name, definition in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE accounts ADD COLUMN {name} {definition}"))


async def _ensure_sqlite_product_columns(conn: AsyncConnection) -> None:
    result = await conn.execute(text("PRAGMA table_info(products)"))
    existing = {row[1] for row in result.fetchall()}
    columns = {
        "commission_rate": "FLOAT DEFAULT 0",
        "rating": "FLOAT DEFAULT 0",
        "payload": "JSON DEFAULT '{}'",
    }
    for name, definition in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE products ADD COLUMN {name} {definition}"))


async def _ensure_sqlite_stock_columns(conn: AsyncConnection) -> None:
    result = await conn.execute(text("PRAGMA table_info(stocks)"))
    existing = {row[1] for row in result.fetchall()}
    if "tenant_id" not in existing:
        await conn.execute(text("ALTER TABLE stocks ADD COLUMN tenant_id VARCHAR(64) DEFAULT ''"))


async def _ensure_sqlite_sales_table(conn: AsyncConnection) -> None:
    await conn.run_sync(lambda sync_conn: Sale.__table__.create(sync_conn, checkfirst=True))


async def _ensure_sqlite_review_columns(conn: AsyncConnection) -> None:
    result = await conn.execute(text("PRAGMA table_info(reviews)"))
    existing = {row[1] for row in result.fetchall()}
    columns = {
        "source": "VARCHAR(32) DEFAULT 'ozon'",
        "payload": "JSON DEFAULT '{}'",
    }
    for name, definition in columns.items():
        if name not in existing:
            await conn.execute(text(f"ALTER TABLE reviews ADD COLUMN {name} {definition}"))
