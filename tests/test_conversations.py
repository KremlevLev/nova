# tests/test_conversations.py
from __future__ import annotations

import tempfile
from pathlib import Path

from modules.storage.database import Database
from modules.storage.conversations import (
    ConversationStore,
)


def test_create_session() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Database(
            Path(directory) / "test.db"
        )
        store = ConversationStore(db)

        session_id = store.create_session()

        assert session_id.startswith("session_")

        db.close()


def test_add_and_get_messages() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Database(
            Path(directory) / "test.db"
        )
        store = ConversationStore(db)

        session_id = store.create_session()

        store.add_message(
            session_id,
            "user",
            "Привет",
        )
        store.add_message(
            session_id,
            "assistant",
            "Здравствуйте",
        )

        messages = store.get_messages(
            session_id
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

        db.close()


def test_delete_session() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Database(
            Path(directory) / "test.db"
        )
        store = ConversationStore(db)

        session_id = store.create_session()
        store.add_message(
            session_id,
            "user",
            "test",
        )

        store.delete_session(session_id)

        messages = store.get_messages(
            session_id
        )

        assert len(messages) == 0

        db.close()
