# tests/test_memories.py
from __future__ import annotations

import tempfile
from pathlib import Path

from modules.storage.database import Database
from modules.storage.memories import MemoryStore


def test_save_and_get_memory() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Database(
            Path(directory) / "test.db"
        )
        store = MemoryStore(db)

        store.save(
            "user_name",
            "Алексей",
            category="preference",
        )

        memory = store.get("user_name")

        assert memory is not None
        assert memory["value"] == "Алексей"
        assert memory["category"] == "preference"

        db.close()


def test_search_memory() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Database(
            Path(directory) / "test.db"
        )
        store = MemoryStore(db)

        store.save(
            "favorite_color",
            "синий",
        )
        store.save(
            "favorite_food",
            "пицца",
        )

        results = store.search("синий")

        assert len(results) >= 1
        assert results[0]["key"] == "favorite_color"

        db.close()


def test_delete_memory() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Database(
            Path(directory) / "test.db"
        )
        store = MemoryStore(db)

        store.save("temp_key", "temp_value")
        store.delete("temp_key")

        memory = store.get("temp_key")

        assert memory is None

        db.close()


def test_clear_all_memories() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = Database(
            Path(directory) / "test.db"
        )
        store = MemoryStore(db)

        store.save("key1", "value1")
        store.save("key2", "value2")

        assert store.count() == 2

        store.clear_all()

        assert store.count() == 0

        db.close()
