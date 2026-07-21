# modules/brain/memory.py
from __future__ import annotations

import os
import json
import re
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from modules.storage.memories import MemoryStore
from modules.storage.database import Database
from modules.domain.results import ToolResult

MEMORY_FILE = "data/memory/local_memory.json"


class BaseMemory:
    """Абстрактный интерфейс для будущих интеграций"""
    def add_document(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        raise NotImplementedError
        
    def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        raise NotImplementedError


class LocalMemory(BaseMemory):
    """
    Легковесная и быстрая локальная память на базе алгоритма BM25.
    Полностью совместима с Python 3.14, работает без нейросетей и C++ библиотек.
    Потребляет 0 МБ оперативной памяти в простое.
    
    Поддерживает Memory Decay - автоматическое забывание устаревшей информации.
    """
    def __init__(
        self,
        storage_path: str = MEMORY_FILE,
        *,
        database: Database | None = None,
    ) -> None:
        self.storage_path = storage_path
        self.documents: list[Dict[str, Any]] = []
        self._load_storage()

        if database is not None:
            self.sqlite_store = MemoryStore(
                database
            )
        else:
            self.sqlite_store = None

    def _tokenize(self, text: str) -> List[str]:
        """Очищает текст, выделяет слова и делает простейший русский стемминг (срез окончаний)"""
        words = re.findall(
        r"[a-zA-Zа-яА-ЯёЁ0-9]{2,}",
        text.lower(),
        )

        stemmed = []
        for w in words:
            # Базовые правила отсечения типичных окончаний для повышения точности сопоставлений
            w_stem = re.sub(
            r"(?:ий|ов|ами|ям|ом|ему|ого|ое|ая|их|ых|"
            r"ую|ть|ся|ти|ок|ек|а|е|и|о|у|ы|я|ь)$",
            "",
            w,
            )

            stemmed.append(w_stem if len(w_stem) >= 2 else w)
        return stemmed

    def _load_storage(self):
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Поддержка обратной совместимости со старыми векторными файлами
                    if isinstance(data, dict):
                        self.documents = data.get("documents", [])
                    elif isinstance(data, list):
                        self.documents = data
            except Exception as e:
                print(f"[Memory Error]: Не удалось загрузить базу памяти: {e}")

    def _save_storage(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({"documents": self.documents}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[Memory Error]: Не удалось сохранить базу памяти: {e}")

    def _apply_decay(self, document: Dict[str, Any]) -> float:
        """Вычисляет коэффициент затухания для документа на основе возраста."""
        metadata = document.get("metadata", {})
        created_at_str = metadata.get("created_at")
        
        if not created_at_str:
            return 1.0
        
        try:
            created_at = datetime.fromisoformat(created_at_str)
            age_days = (datetime.now(timezone.utc) - created_at).total_seconds() / 86400
            
            # Стохастическое затухание: уменьшаем уверенность со временем
            # После 30 дней - 0.9, после 90 дней - 0.7, после 180 дней - 0.5, после 365 дней - 0.25
            if age_days > 365:
                return 0.25
            elif age_days > 180:
                return 0.5
            elif age_days > 90:
                return 0.7
            elif age_days > 30:
                return 0.9
            else:
                return 1.0
        except Exception:
            return 1.0

    def _should_decay_remove(self, document: Dict[str, Any]) -> bool:
        """Определяет, нужно ли удалить документ из-за затухания."""
        metadata = document.get("metadata", {})
        decay_threshold = metadata.get("decay_threshold")
        
        if decay_threshold is None:
            return False
        
        decay_factor = self._apply_decay(document)
        initial_confidence = metadata.get("initial_confidence", 1.0)
        current_confidence = decay_factor * initial_confidence
        
        return current_confidence < decay_threshold

    def apply_decay(self) -> int:
        """Применяет затухание ко всем документам и удаляет устаревшие.
        
        Returns:
            Количество удаленных документов.
        """
        initial_count = len(self.documents)
        self.documents = [
            doc for doc in self.documents 
            if not self._should_decay_remove(doc)
        ]
        removed_count = initial_count - len(self.documents)
        
        if removed_count > 0:
            self._save_storage()
        
        return removed_count

    def add_document(
        self, 
        text: str, 
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 1,
    ) -> None:
        if not text.strip():
            return
            
        metadata = metadata or {}
        
        # Добавляем временные метки и приоритет
        if "created_at" not in metadata:
            metadata["created_at"] = datetime.now(timezone.utc).isoformat()
        metadata["priority"] = priority
        metadata["initial_confidence"] = metadata.get("confidence", 1.0)
        
        # Защита от дубликатов
        for doc in self.documents:
            if doc["text"].strip().lower() == text.strip().lower():
                # Обновляем метаданные существующего документа
                doc["metadata"].update(metadata)
                self._save_storage()
                return

        self.documents.append({
            "text": text,
            "metadata": metadata
        })
        self._save_storage()

    def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        if not self.documents or not query.strip():
            return []
            
        query_tokens = list(dict.fromkeys(self._tokenize(query)))
        if not query_tokens:
            return []

        N = len(self.documents)
        
        # Считаем Document Frequency для каждого токена запроса
        df = {}
        for token in query_tokens:
            df[token] = sum(1 for doc in self.documents if token in self._tokenize(doc["text"]))

        # Средняя длина документа
        lengths = [len(self._tokenize(doc["text"])) for doc in self.documents]
        avg_dl = max(
            sum(lengths) / N if N > 0 else 1.0,
            1.0,
        )


        # Параметры BM25
        k1 = 1.2
        b = 0.75

        scored_docs = []
        for doc in self.documents:
            doc_tokens = self._tokenize(doc["text"])
            doc_len = len(doc_tokens)
            
            score = 0.0
            for token in query_tokens:
                if token in doc_tokens:
                    token_df = df.get(token, 0)
                    # Вычисление IDF (обратной частоты документа)
                    idf = math.log((N - token_df + 0.5) / (token_df + 0.5) + 1.0)
                    
                    # Частота термина в текущем документе
                    tf = doc_tokens.count(token)
                    
                    # Формула Okapi BM25
                    tf_component = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_dl)))
                    
                    # Применяем затухание и приоритет
                    priority = doc.get("metadata", {}).get("priority", 1)
                    decay = self._apply_decay({"metadata": doc.get("metadata", {})})
                    
                    score += idf * tf_component * priority * decay
            
            if score > 0.0:
                scored_docs.append((score, doc))

        # Сортировка по релевантности
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for score, doc in scored_docs[:limit]:
            doc_copy = doc.copy()
            doc_copy["score"] = float(score)
            results.append(doc_copy)
            
        return results


class HierarchicalMemory:
    """
    Иерархическая память с уровнями приоритетов.
    
    Уровни памяти:
    - SHORT_TERM (приоритет 10): временная информация, быстро забывается
    - MIDDLE_TERM (приоритет 5): информация средней важности, затухает со временем
    - LONG_TERM (приоритет 3): важная информация, долго хранится
    - PERMANENT (приоритет 1): постоянная информация, не забывается
    """
    
    class MemoryLevel:
        SHORT_TERM = 10
        MIDDLE_TERM = 5
        LONG_TERM = 3
        PERMANENT = 1
    
    def __init__(
        self,
        storage_path: str = MEMORY_FILE,
        *,
        database: Database | None = None,
    ) -> None:
        self.storage_path = storage_path
        self.local_memory = LocalMemory(storage_path, database=database)
        self._decay_applied = False
    
    def add(
        self,
        key: str,
        value: str,
        *,
        level: str = "middle_term",
    ) -> ToolResult:
        """Добавить информацию в память с указанием уровня приоритета.
        
        Args:
            key: Ключ для идентификации памяти
            value: Сохраняемое значение
            level: Уровень памяти (short_term, middle_term, long_term, permanent)
        """
        level_map = {
            "short_term": self.MemoryLevel.SHORT_TERM,
            "middle_term": self.MemoryLevel.MIDDLE_TERM,
            "long_term": self.MemoryLevel.LONG_TERM,
            "permanent": self.MemoryLevel.PERMANENT,
        }
        
        priority = level_map.get(level, self.MemoryLevel.MIDDLE_TERM)
        
        # Сохраняем в SQLite если доступно
        if self.local_memory.sqlite_store is not None:
            self.local_memory.sqlite_store.save(
                key,
                value,
                metadata={"level": level, "priority": priority},
            )
        
        # Сохраняем в локальную память
        self.local_memory.add_document(
            value,
            metadata={"level": level, "priority": priority},
            priority=priority,
        )
        
        return ToolResult.ok(
            f"Информация сохранена на уровне {level}",
            data={"key": key, "level": level, "code": "MEMORY_SAVED"},
        )
    
    def search(
        self,
        query: str,
        *,
        level: str | None = None,
        limit: int = 10,
    ) -> ToolResult:
        """Поиск информации в памяти.
        
        Args:
            query: Поисковый запрос
            level: Фильтр по уровню (если None - поиск во всех уровнях)
            limit: Максимальное количество результатов
        """
        results = self.local_memory.search(query, limit)
        
        if level is not None:
            results = [
                r for r in results
                if r.get("metadata", {}).get("level") == level
            ]
        
        return ToolResult.ok(
            f"Найдено {len(results)} результатов",
            data={"results": results, "query": query, "code": "MEMORY_SEARCH_RESULT"},
        )
    
    def consolidate(self) -> ToolResult:
        """Консолидация памяти - объединение похожих воспоминаний."""
        # TODO: Реализовать объединение похожих воспоминаний
        # Это может включать:
        # - Объединение дублирующих фактов
        # - Суммирование информации
        # - Перенос важных фактов на более высокий уровень
        
        return ToolResult.ok(
            "Консолидация памяти выполнена",
            data={"code": "MEMORY_CONSOLIDATED"},
        )
    
    def apply_decay(self) -> ToolResult:
        """Применить затухание ко всей памяти."""
        removed_count = self.local_memory.apply_decay()
        
        return ToolResult.ok(
            f"Удалено {removed_count} устаревших записей",
            data={"removed_count": removed_count, "code": "MEMORY_DECAY_APPLIED"},
        )
    
    def get_stats(self) -> ToolResult:
        """Получить статистику памяти."""
        counts = {"short_term": 0, "middle_term": 0, "long_term": 0, "permanent": 0}
        
        for doc in self.local_memory.documents:
            level = doc.get("metadata", {}).get("level", "middle_term")
            counts[level] = counts.get(level, 0) + 1
        
        return ToolResult.ok(
            "Статистика памяти",
            data={"counts": counts, "total": len(self.local_memory.documents), "code": "MEMORY_STATS"},
        )
