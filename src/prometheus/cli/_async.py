"""Small helper so Typer's sync command handlers can call async services."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable


def run[T](coro: Awaitable[T]) -> T:
    return asyncio.run(coro)


def ensure_db_ready() -> None:
    from prometheus.db.session import init_db

    asyncio.run(init_db())
