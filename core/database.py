from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_database_url, use_postgres

_ENGINE = None
_SESSION_FACTORY: async_sessionmaker[AsyncSession] | None = None


def init_engine():
    global _ENGINE, _SESSION_FACTORY  # noqa: PLW0603
    if _ENGINE is None:
        url = get_database_url()
        kwargs = {"future": True, "pool_pre_ping": True}
        if use_postgres():
            # asyncpg needs ssl=True for Vercel Postgres (sslmode stripped from URL)
            kwargs["connect_args"] = {"ssl": True}
        _ENGINE = create_async_engine(url, **kwargs)
        _SESSION_FACTORY = async_sessionmaker(_ENGINE, expire_on_commit=False)
    return _ENGINE


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _SESSION_FACTORY is None:
        init_engine()
    assert _SESSION_FACTORY is not None
    return _SESSION_FACTORY


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
