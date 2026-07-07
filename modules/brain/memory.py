# modules/brain/memory.py
import os
import json
import numpy as np
from typing import List, Dict, Any, Optional
from semantic_router.encoders import FastEmbedEncoder

class BaseMemory:
    """Абстрактный интерфейс для будущих интеграций (например, ChromaDB)"""
    def add_document(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        raise NotImplementedError
        
    def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        raise NotImplementedError


class LocalVectorMemory(BaseMemory):
    """
    Модульная векторная память на базе NumPy и FastEmbed.
    Идеально совместима с Python 3.14 и не требует C++ компиляторов.
    """
    def __init__(self, storage_path: str = "data/memory/local_memory.json", encoder: Optional[FastEmbedEncoder] = None):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        # Переиспользуем готовый энкодер из роутера, либо создаем новый во избежание дублирования в RAM
        if encoder:
            self.encoder = encoder
        else:
            self.encoder = FastEmbedEncoder(name="intfloat/multilingual-e5-large")
            
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: List[List[float]] = []
        self._load_storage()

    def _load_storage(self):
        """Загружает базу из JSON-файла"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.documents = data.get("documents", [])
                    self.embeddings = data.get("embeddings", [])
            except Exception as e:
                print(f"[Memory Error]: Не удалось загрузить базу памяти: {e}")

    def _save_storage(self):
        """Сохраняет базу в JSON-файл"""
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({
                    "documents": self.documents,
                    "embeddings": self.embeddings
                }, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[Memory Error]: Не удалось сохранить базу памяти: {e}")

    def add_document(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Добавляет текст, генерирует для него вектор E5 и сохраняет в БД"""
        if not text.strip():
            return
            
        try:
            # Генерация эмбеддинга через FastEmbed
            vector = self.encoder([text])[0]
            
            # Сохраняем документ и его вектор
            self.documents.append({
                "text": text,
                "metadata": metadata or {}
            })
            self.embeddings.append(vector)
            self._save_storage()
        except Exception as e:
            print(f"[Memory Error]: Ошибка добавления документа: {e}")

    def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Ищет похожие записи по косинусному сходству"""
        if not self.documents or not query.strip():
            return []
            
        try:
            # Получаем вектор запроса
            query_vector = np.array(self.encoder([query])[0])
            
            # Конвертируем сохраненные векторы в матрицу NumPy
            matrix = np.array(self.embeddings)
            
            # Вычисляем косинусное сходство (Cosine Similarity)
            # Dot Product / (Norm(A) * Norm(B))
            dot_products = np.dot(matrix, query_vector)
            matrix_norms = np.linalg.norm(matrix, axis=1)
            query_norm = np.linalg.norm(query_vector)
            
            # Защита от деления на ноль
            norms = matrix_norms * query_norm
            norms[norms == 0] = 1e-9
            
            similarities = dot_products / norms
            
            # Сортируем индексы по убыванию схожести
            top_indices = np.argsort(similarities)[::-1][:limit]
            
            results = []
            for idx in top_indices:
                # Возвращаем документ с добавленной метрикой схожести (score)
                doc = self.documents[idx].copy()
                doc["score"] = float(similarities[idx])
                results.append(doc)
                
            return results
        except Exception as e:
            print(f"[Memory Error]: Ошибка поиска в памяти: {e}")
            return []