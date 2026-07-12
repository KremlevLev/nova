# modules/storage/memories.py
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from modules.storage.database import Database


logger = logging.getLogger("Memories")


class MemoryStore:
    """
    Долговременная память Nova в SQLite.

    Позволяет:
    - сохранять факты;
    - искать по ключевым словам;
    - удалять факты;
    - очищать всю память.
    """

    def __init__(
        self,
        database: Database,
    ) -> None:
        self.db = database

    def save(
        self,
        key: str,
        value: str,
        *,
        category: str = "general",
        source: str = "user",
        confidence: float = 1.0,
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        self.db.execute(
            """
            INSERT INTO memories
                (key, value, category, source,
                 confidence, expires_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                category = excluded.category,
                source = excluded.source,
                confidence = excluded.confidence,
                expires_at = excluded.expires_at,
                metadata = excluded.metadata,
                updated_at = datetime('now')
            """,
            (
                key,
                value,
                category,
                source,
                min(1.0, max(0.0, confidence)),
                expires_at,
                json.dumps(
                    metadata or {},
                    ensure_ascii=False,
                ),
            ),
        )

        self.db.commit()

        return True

    def get(
        self,
        key: str,
    ) -> dict[str, Any] | None:
        row = self.db.fetchone(
            """
            SELECT key, value, category, source,
                   confidence, created_at, updated_at,
                   expires_at, metadata
            FROM memories
            WHERE key = ?
            """,
            (key,),
        )

        if row is None:
            return None

        if row.get("expires_at"):
            expires = datetime.fromisoformat(
                row["expires_at"]
            )

            if expires < datetime.now(
                timezone.utc
            ):
                self.delete(key)
                return None

        return row

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        search_term = f"%{query}%"

        rows = self.db.fetchall(
            """
            SELECT key, value, category, source,
                   confidence, created_at, updated_at,
                   expires_at, metadata
            FROM memories
            WHERE key LIKE ?
               OR value LIKE ?
               OR category LIKE ?
            ORDER BY confidence DESC, updated_at DESC
            LIMIT ?
            """,
            (search_term, search_term, search_term, limit),
        )

        return rows

    def delete(
        self,
        key: str,
    ) -> bool:
        self.db.execute(
            "DELETE FROM memories WHERE key = ?",
            (key,),
        )
        self.db.commit()

        return True

    def clear_all(self) -> bool:
        self.db.execute(
            "DELETE FROM memories"
        )
        self.db.commit()

        return True

    def list_by_category(
        self,
        category: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.db.fetchall(
            """
            SELECT key, value, category, source,
                   confidence, created_at, updated_at,
                   expires_at, metadata
            FROM memories
            WHERE category = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (category, limit),
        )

    def count(self) -> int:
        row = self.db.fetchone(
            "SELECT COUNT(*) as count FROM memories"
        )

        return row["count"] if row else 0
