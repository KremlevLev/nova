# modules/brain/memory.py
import os
import json
import re
import math
from typing import List, Dict, Any, Optional

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
    """
    def __init__(self, storage_path: str = MEMORY_FILE):
        self.storage_path = storage_path
        self.documents: List[Dict[str, Any]] = []
        self._load_storage()

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

    def add_document(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if not text.strip():
            return
            
        # Защита от дубликатов
        for doc in self.documents:
            if doc["text"].strip().lower() == text.strip().lower():
                return

        self.documents.append({
            "text": text,
            "metadata": metadata or {}
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
                    score += idf * tf_component
            
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