"""Append-only audit rows. The live desk reads the in-memory tape first."""

from __future__ import annotations

import json
from pathlib import Path

import aiosqlite


class AuditStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.path)
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        await self.db.commit()

    async def add(self, ts: str, event_type: str, payload: dict) -> None:
        if self.db is None:
            return
        await self.db.execute(
            "INSERT INTO audit (ts, event_type, payload) VALUES (?, ?, ?)",
            (ts, event_type, json.dumps(payload, default=str)),
        )
        await self.db.commit()

    async def count(self) -> int:
        if self.db is None:
            return 0
        cursor = await self.db.execute("SELECT COUNT(*) FROM audit")
        row = await cursor.fetchone()
        return int(row[0] if row else 0)

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None
