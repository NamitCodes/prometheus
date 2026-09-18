"""Async engine/session factory for the application database."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from prometheus.config import settings

if settings.app_database_url.startswith("sqlite"):
    db_file = settings.app_database_url.rsplit("///", 1)[-1]
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(settings.app_database_url)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    from prometheus.db import models  # noqa: F401  -- registers models on Base.metadata
    from prometheus.db.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
