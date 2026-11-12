"""Async SQLite access.

One short-lived connection per unit of work keeps the async server simple:
aiosqlite runs every statement on its own thread, so no connection is ever
shared across request tasks.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Iterable, Sequence

import aiosqlite

from . import config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


async def connect(path: Path | str | None = None) -> aiosqlite.Connection:
    db_path = Path(path or config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    await db.execute("PRAGMA journal_mode = WAL")
    await db.execute("PRAGMA busy_timeout = 5000")
    return db


@asynccontextmanager
async def open_db(path: Path | str | None = None):
    db = await connect(path)
    try:
        yield db
    finally:
        await db.close()


async def init_db(path: Path | str | None = None) -> None:
    """Create the schema if it is missing. Safe to call on every boot."""
    db_path = Path(path or config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    db = await connect(db_path)
    try:
        await db.executescript(schema)
        await db.commit()
    finally:
        await db.close()


async def query_all(db: aiosqlite.Connection, sql: str, params: Sequence[Any] = ()) -> list[aiosqlite.Row]:
    async with db.execute(sql, tuple(params)) as cursor:
        return list(await cursor.fetchall())


async def query_one(db: aiosqlite.Connection, sql: str, params: Sequence[Any] = ()) -> aiosqlite.Row | None:
    async with db.execute(sql, tuple(params)) as cursor:
        return await cursor.fetchone()


async def execute(db: aiosqlite.Connection, sql: str, params: Sequence[Any] = ()) -> int:
    """Run a write statement and return the number of affected rows."""
    cursor = await db.execute(sql, tuple(params))
    await db.commit()
    changed = cursor.rowcount
    await cursor.close()
    return changed


async def execute_many(db: aiosqlite.Connection, sql: str, rows: Iterable[Sequence[Any]]) -> None:
    await db.executemany(sql, [tuple(row) for row in rows])
    await db.commit()


async def insert(db: aiosqlite.Connection, sql: str, params: Sequence[Any] = ()) -> int:
    """Run an INSERT and return the new row id."""
    cursor = await db.execute(sql, tuple(params))
    await db.commit()
    row_id = cursor.lastrowid
    await cursor.close()
    return int(row_id or 0)
