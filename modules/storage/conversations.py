# modules/storage/conversations.py
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from modules.storage.database import Database


logger = logging.getLogger("Conversations")


class ConversationStore:
    """
    Хранит историю диалогов в SQLite.

    Позволяет:
    - создавать сессии;
    - добавлять сообщения;
    - получать историю сессии;
    - удалять сессии.
    """

    def __init__(
        self,
        database: Database,
    ) -> None:
        self.db = database

    def create_session(
        self,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        resolved_id = (
            session_id
            or f"session_{uuid.uuid4().hex}"
        )

        self.db.execute(
            """
            INSERT OR IGNORE INTO sessions
                (session_id, metadata)
            VALUES (?, ?)
            """,
            (
                resolved_id,
                json.dumps(
                    metadata or {},
                    ensure_ascii=False,
                ),
            ),
        )

        self.db.commit()

        return resolved_id

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        *,
        token_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        self.db.execute(
            """
            INSERT INTO messages
                (session_id, role, content,
                 token_count, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                token_count,
                json.dumps(
                    metadata or {},
                    ensure_ascii=False,
                ),
            ),
        )

        self.db.execute(
            """
            UPDATE sessions
            SET updated_at = datetime('now')
            WHERE session_id = ?
            """,
            (session_id,),
        )

        self.db.commit()

        return self.db.fetchone(
            "SELECT last_insert_rowid()"
        )["last_insert_rowid()"]

    def get_messages(
        self,
        session_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self.db.fetchall(
            """
            SELECT message_id, role, content,
                   created_at, token_count, metadata
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            LIMIT ? OFFSET ?
            """,
            (session_id, limit, offset),
        )

    def get_recent_messages(
        self,
        session_id: str,
        *,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        return self.db.fetchall(
            """
            SELECT message_id, role, content,
                   created_at, token_count, metadata
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, count),
        )

    def delete_session(
        self,
        session_id: str,
    ) -> bool:
        self.db.execute(
            "DELETE FROM messages WHERE session_id = ?",
            (session_id,),
        )
        self.db.execute(
            "DELETE FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        self.db.commit()

        return True

    def list_sessions(
        self,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.db.fetchall(
            """
            SELECT session_id, created_at,
                   updated_at, metadata
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
