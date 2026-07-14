# tests/test_crash_recovery.py
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from modules.storage.database import Database
from modules.storage.conversations import (
    ConversationStore,
)
from modules.storage.memories import MemoryStore
from modules.windows.process_manager import (
    ProcessManager,
)


def test_database_survives_reopen() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "test.db"

        db = Database(db_path)
        store = ConversationStore(db)

        session_id = store.create_session()
        store.add_message(
            session_id,
            "user",
            "Привет",
        )

        db.close()

        db2 = Database(db_path)
        store2 = ConversationStore(db2)

        messages = store2.get_messages(
            session_id
        )

        assert len(messages) == 1
        assert messages[0]["content"] == "Привет"

        db2.close()


def test_memory_survives_reopen() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "test.db"

        db = Database(db_path)
        store = MemoryStore(db)

        store.save(
            "test_key",
            "test_value",
        )

        db.close()

        db2 = Database(db_path)
        store2 = MemoryStore(db2)

        memory = store2.get("test_key")

        assert memory is not None
        assert memory["value"] == "test_value"

        db2.close()


def test_process_manager_restores_metadata() -> None:
    with tempfile.TemporaryDirectory() as directory:
        import os

        original_cwd = os.getcwd()

        try:
            os.chdir(directory)

            manager = ProcessManager()

            result = manager.start_process(
                [
                    "python",
                    "-c",
                    "import time; time.sleep(5)",
                ],
                label="restore_test",
            )

            assert result.success

            process_id = result.data[
                "process_id"
            ]

            # Симулируем перезапуск.
            manager2 = ProcessManager()

            status_result = (
                manager2.get_process_status(
                    process_id
                )
            )

            assert status_result.success
            assert (
                status_result.data["label"]
                == "restore_test"
            )

            manager2.cleanup_all()

        finally:
            os.chdir(original_cwd)
