# modules/tools/synthesis.py
"""Research Synthesis - объединение информации из разных источников.

Позволяет синтезировать ответы из нескольких источников в единый ответ.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger("Synthesis")


@dataclass
class Source:
    """Источник информации."""
    url: str
    title: str
    content: str
    credibility_score: float = 0.5  # 0.0 - 1.0


@dataclass
class SynthesizedResult:
    """Результат синтеза."""
    summary: str
    key_points: list[str]
    sources: list[Source]
    confidence: float


class ResearchSynthesizer:
    """
    Синтезирует информацию из нескольких источников.
    
    Анализирует контент, выделяет ключевые моменты и формирует
    объединённый ответ с указанием источников.
    """
    
    def __init__(self, llm: Any = None) -> None:
        """
        Инициализация синтезатора.
        
        Args:
            llm: LLM для анализа (опционально, можно использовать rule-based)
        """
        self.llm = llm
    
    def synthesize(
        self,
        query: str,
        sources: list[Source],
    ) -> SynthesizedResult:
        """
        Синтезировать ответ из источников.
        
        Args:
            query: исходный запрос
            sources: список источников
            
        Returns:
            Синтезированный результат
        """
        if not sources:
            return SynthesizedResult(
                summary="Нет доступных источников для синтеза.",
                key_points=[],
                sources=[],
                confidence=0.0,
            )
        
        # Сортируем по credibility_score
        sorted_sources = sorted(
            sources,
            key=lambda s: s.credibility_score,
            reverse=True,
        )
        
        # Выделяем ключевые моменты
        key_points = self._extract_key_points(sorted_sources)
        
        # Формируем краткий обзор
        summary = self._create_summary(query, sorted_sources, key_points)
        
        # Вычисляем общую уверенность
        avg_credibility = sum(s.credibility_score for s in sources) / len(sources)
        
        return SynthesizedResult(
            summary=summary,
            key_points=key_points,
            sources=sorted_sources,
            confidence=min(avg_credibility, 0.95),
        )
    
    def _extract_key_points(self, sources: list[Source]) -> list[str]:
        """Извлечь ключевые моменты из источников."""
        points = []
        
        for source in sources[:5]:  # Ограничиваем до 5 источников
            content = source.content[:500]  # Берём первые 500 символов
            
            # Простой rule-based поиск ключевых фраз
            sentences = self._split_sentences(content)
            
            for sentence in sentences[:3]:  # По 3 предложения от источника
                if len(sentence) > 30:  # Фильтруем короткие
                    points.append(f"{source.title}: {sentence}")
        
        return points[:10]  # Общий лимит 10 ключевых моментов
    
    def _create_summary(
        self,
        query: str,
        sources: list[Source],
        key_points: list[str],
    ) -> str:
        """Создать краткий обзор."""
        if not sources:
            return "Не найдено информации по запросу."
        
        # Формируем summary из ключевых моментов
        summary_lines = [
            f"По запросу '{query}' найдено {len(sources)} источников.",
            "",
        ]
        
        if key_points:
            summary_lines.append("Основные выводы:")
            summary_lines.extend(f"• {point}" for point in key_points[:5])
        
        summary_lines.extend([
            "",
            f"Источники: {', '.join(s.title for s in sources[:3])}",
        ])
        
        return "\n".join(summary_lines)
    
    def _split_sentences(self, text: str) -> list[str]:
        """Разделить текст на предложения."""
        # Простой разбор по знакам препинания
        import re
        sentences = re.split(r"[.!?]+", text)
        return [s.strip() for s in sentences if s.strip()]


def create_synthesis_tool(synthesizer: ResearchSynthesizer) -> dict[str, Any]:
    """
    Создать tool definition для синтеза исследований.
    
    Returns:
        Schema инструмента
    """
    return {
        "function": {
            "name": "synthesize_research",
            "description": "Объединить информацию из разных источников в единый ответ",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Исходный запрос для контекста",
                    },
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string"},
                                "title": {"type": "string"},
                                "content": {"type": "string"},
                                "credibility_score": {"type": "number"},
                            },
                        },
                    },
                },
                "required": ["query", "sources"],
            },
        },
    }


async def run_synthesis(
    query: str,
    sources_data: list[dict[str, Any]],
    synthesizer: ResearchSynthesizer,
) -> dict[str, Any]:
    """
    Выполнить синтез исследований.
    
    Args:
        query: исходный запрос
        sources_data: данные источников
        synthesizer: синтезатор
        
    Returns:
        Результат синтеза
    """
    sources = [
        Source(
            url=s.get("url", ""),
            title=s.get("title", "Без названия"),
            content=s.get("content", ""),
            credibility_score=s.get("credibility_score", 0.5),
        )
        for s in sources_data
    ]
    
    result = synthesizer.synthesize(query, sources)
    
    return {
        "summary": result.summary,
        "key_points": result.key_points,
        "confidence": result.confidence,
        "sources_count": len(sources),
        "sources": [
            {"url": s.url, "title": s.title}
            for s in result.sources
        ],
    }