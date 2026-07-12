# tests/test_database.py
from __future__ import annotations

import tempfile
from pathlib import Path

from modules.storage.database import Database


def test_database_creates_tables() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "test.db"
        db = Database(db_path)

        tables = db.fetchall(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' "
            "ORDER BY name"
        )

        table_names = [
            t["name"] for t in tables
        ]

        assert "sessions" in table_names
        assert "messages" in table_names
        assert "memories" in table_names

        db.close()


def test_insert_and_select() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Database(
            Path(directory) / "test.db"
        )

        db.execute(
            "INSERT INTO sessions (session_id) "
            "VALUES (?)",
            ("test-session",),
        )
        db.commit()

        row = db.fetchone(
            "SELECT session_id FROM sessions "
            "WHERE session_id = ?",
            ("test-session",),
        )

        assert row is not None
        assert row["session_id"] == "test-session"

        db.close()
