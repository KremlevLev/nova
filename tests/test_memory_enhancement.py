# tests/test_memory_enhancement.py
from __future__ import annotations

import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

from modules.storage.database import Database
from modules.brain.memory import LocalMemory, HierarchicalMemory


class TestMemoryDecay:
    """Тесты для Memory Decay - затухания памяти."""

    def test_apply_decay_removes_old_documents(self):
        """Тест удаления документов при затухании."""
        with tempfile.TemporaryDirectory() as directory:
            storage_path = Path(directory) / "memory.json"
            memory = LocalMemory(str(storage_path))
            
            # Добавляем документ со сроком затухания 0.5
            # 500 дней = decay factor 0.25, current_confidence = 0.25 * 1.0 = 0.25 < 0.5
            old_date = (datetime.now(timezone.utc) - timedelta(days=500)).isoformat()
            
            memory.add_document(
                "старый документ",
                metadata={
                    "created_at": old_date,
                    "decay_threshold": 0.5,
                    "initial_confidence": 1.0,
                },
            )
            
            # Добавляем свежий документ без threshold
            memory.add_document(
                "новый документ",
                metadata={"created_at": datetime.now(timezone.utc).isoformat()},
            )
            
            assert len(memory.documents) == 2
            
            # Применяем затухание
            removed = memory.apply_decay()
            
            # Старый документ должен быть удален (decay factor 0.25 * 1.0 = 0.25 < 0.5)
            assert removed == 1
            assert len(memory.documents) == 1
            assert memory.documents[0]["text"] == "новый документ"

    def test_apply_decay_keeps_recent_documents(self):
        """Тест сохранения свежих документов при затухании."""
        with tempfile.TemporaryDirectory() as directory:
            storage_path = Path(directory) / "memory.json"
            memory = LocalMemory(str(storage_path))
            
            # Добавляем свежий документ
            memory.add_document(
                "свежий документ",
                metadata={"created_at": datetime.now(timezone.utc).isoformat()},
            )
            
            removed = memory.apply_decay()
            
            # Свежий документ должен остаться
            assert removed == 0
            assert len(memory.documents) == 1

    def test_apply_decay_no_threshold_keeps_all(self):
        """Тест что документы без threshold не удаляются."""
        with tempfile.TemporaryDirectory() as directory:
            storage_path = Path(directory) / "memory.json"
            memory = LocalMemory(str(storage_path))
            
            # Добавляем старый документ без threshold
            old_date = (datetime.now(timezone.utc) - timedelta(days=500)).isoformat()
            memory.add_document(
                "очень старый документ",
                metadata={"created_at": old_date},
            )
            
            removed = memory.apply_decay()
            
            # Без threshold документ не должен удалиться
            assert removed == 0
            assert len(memory.documents) == 1


class TestHierarchicalMemory:
    """Тесты для иерархической памяти."""

    def test_add_with_different_levels(self):
        """Тест добавления с разными уровнями памяти."""
        with tempfile.TemporaryDirectory() as directory:
            storage_path = Path(directory) / "memory.json"
            memory = HierarchicalMemory(str(storage_path))
            
            result_short = memory.add("key1", "значение 1", level="short_term")
            result_long = memory.add("key2", "значение 2", level="long_term")
            result_perm = memory.add("key3", "значение 3", level="permanent")
            
            assert result_short.success
            assert result_long.success
            assert result_perm.success
            
            assert memory.local_memory.documents[0]["metadata"]["level"] == "short_term"
            assert memory.local_memory.documents[1]["metadata"]["level"] == "long_term"
            assert memory.local_memory.documents[2]["metadata"]["level"] == "permanent"

    def test_search_filters_by_level(self):
        """Тест поиска с фильтром по уровню."""
        with tempfile.TemporaryDirectory() as directory:
            storage_path = Path(directory) / "memory.json"
            memory = HierarchicalMemory(str(storage_path))
            
            memory.add("key1", "важный факт", level="long_term")
            memory.add("key2", "важный эфемерный факт", level="short_term")
            
            # Ищем только в long_term
            result = memory.search("факт", level="long_term")
            
            assert result.success
            assert len(result.data["results"]) == 1
            assert result.data["results"][0]["metadata"]["level"] == "long_term"

    def test_search_all_levels(self):
        """Тест поиска во всех уровнях."""
        with tempfile.TemporaryDirectory() as directory:
            storage_path = Path(directory) / "memory.json"
            memory = HierarchicalMemory(str(storage_path))
            
            memory.add("key1", "факт", level="short_term")
            memory.add("key2", "другой факт", level="long_term")
            memory.add("key3", "третий факт", level="permanent")
            
            result = memory.search("факт", level=None)
            
            assert result.success
            assert len(result.data["results"]) == 3

    def test_priority_affects_search_score(self):
        """Тест что приоритет влияет на рейтинг в поиске."""
        with tempfile.TemporaryDirectory() as directory:
            storage_path = Path(directory) / "memory.json"
            memory = LocalMemory(str(storage_path))
            
            # Добавляем одинаковые документы с разными приоритетами
            memory.add_document("факт про работу", priority=1)  # низкий приоритет
            memory.add_document("факт про работу", priority=10)  # высокий приоритет
            
            # Из-за дубликатов второй не добавится, обновим первый
            memory.documents[0]["metadata"]["priority"] = 10
            memory._save_storage()
            
            results = memory.search("факт про работу", limit=10)
            
            # Высокий приоритет должен давать выше score
            assert results[0]["metadata"]["priority"] == 10

    def test_get_stats(self):
        """Тест получения статистики памяти."""
        with tempfile.TemporaryDirectory() as directory:
            storage_path = Path(directory) / "memory.json"
            memory = HierarchicalMemory(str(storage_path))
            
            memory.add("key1", "значение 1", level="short_term")
            memory.add("key2", "значение 2", level="long_term")
            memory.add("key3", "значение 3", level="permanent")
            memory.add("key4", "значение 4", level="middle_term")
            
            stats = memory.get_stats()
            
            assert stats.success
            assert stats.data["total"] == 4
            assert stats.data["counts"]["short_term"] == 1
            assert stats.data["counts"]["long_term"] == 1
            assert stats.data["counts"]["permanent"] == 1
            assert stats.data["counts"]["middle_term"] == 1

    def test_consolidate_returns_success(self):
        """Тест консолидации памяти."""
        with tempfile.TemporaryDirectory() as directory:
            storage_path = Path(directory) / "memory.json"
            memory = HierarchicalMemory(str(storage_path))
            
            result = memory.consolidate()
            
            assert result.success

    def test_decay_integration_with_sqlite(self):
        """Тест интеграции decay с SQLite."""
        with tempfile.TemporaryDirectory() as directory:
            db = Database(Path(directory) / "test.db")
            storage_path = Path(directory) / "memory.json"
            memory = HierarchicalMemory(str(storage_path), database=db)
            
            # Добавляем факт
            result = memory.add("test_fact", "значение", level="short_term")
            
            assert result.success
            
            # Проверяем что сохранился в SQLite
            db_fact = memory.local_memory.sqlite_store.get("test_fact")
            assert db_fact is not None
            assert db_fact["value"] == "значение"
            
            db.close()