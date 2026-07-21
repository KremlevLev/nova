# tests/test_synthesis.py
from __future__ import annotations

from modules.tools.synthesis import (
    Source,
    SynthesizedResult,
    ResearchSynthesizer,
    create_synthesis_tool,
)


def test_source_creation() -> None:
    """Тест создания источника."""
    source = Source(
        url="https://example.com",
        title="Example",
        content="Test content",
    )
    
    assert source.url == "https://example.com"
    assert source.title == "Example"
    assert source.content == "Test content"
    assert source.credibility_score == 0.5  # Значение по умолчанию


def test_source_with_custom_credibility() -> None:
    """Тест источника с кастомным credibility_score."""
    source = Source(
        url="https://example.com",
        title="Example",
        content="Test content",
        credibility_score=0.8,
    )
    
    assert source.credibility_score == 0.8


def test_synthesized_result_creation() -> None:
    """Тест создания результата синтеза."""
    result = SynthesizedResult(
        summary="Test summary",
        key_points=["point 1", "point 2"],
        sources=[],
        confidence=0.9,
    )
    
    assert result.summary == "Test summary"
    assert len(result.key_points) == 2
    assert result.confidence == 0.9


def test_research_synthesizer_creation() -> None:
    """Тест создания синтезатора."""
    synthesizer = ResearchSynthesizer()
    
    assert synthesizer.llm is None


def test_synthesize_empty_sources() -> None:
    """Тест синтеза без источников."""
    synthesizer = ResearchSynthesizer()
    
    result = synthesizer.synthesize("test query", [])
    
    assert result.summary == "Нет доступных источников для синтеза."
    assert result.key_points == []
    assert result.confidence == 0.0


def test_synthesize_single_source() -> None:
    """Тест синтеза с одним источником."""
    synthesizer = ResearchSynthesizer()
    
    sources = [
        Source(
            url="https://example.com",
            title="Example",
            content="Это тестовый контент для синтеза информации. Должен быть обработан.",
            credibility_score=0.9,
        ),
    ]
    
    result = synthesizer.synthesize("test query", sources)
    
    assert "test query" in result.summary
    assert len(sources) == 1
    assert result.confidence == 0.9


def test_synthesize_multiple_sources() -> None:
    """Тест синтеза с несколькими источниками."""
    synthesizer = ResearchSynthesizer()
    
    sources = [
        Source(
            url="https://example1.com",
            title="Source 1",
            content="Контент первого источника для анализа.",
            credibility_score=0.9,
        ),
        Source(
            url="https://example2.com",
            title="Source 2",
            content="Контент второго источника для анализа.",
            credibility_score=0.7,
        ),
    ]
    
    result = synthesizer.synthesize("test query", sources)
    
    assert len(sources) == 2
    # Средний credibility_score = 0.8
    assert result.confidence == 0.8


def test_synthesize_sorts_by_credibility() -> None:
    """Тест сортировки источников по credibility."""
    synthesizer = ResearchSynthesizer()
    
    sources = [
        Source(url="url3", title="Low", content="Content", credibility_score=0.3),
        Source(url="url1", title="High", content="Content", credibility_score=0.9),
        Source(url="url2", title="Medium", content="Content", credibility_score=0.6),
    ]
    
    result = synthesizer.synthesize("query", sources)
    
    # Источники должны быть отсортированы по убыванию credibility
    assert result.sources[0].credibility_score == 0.9
    assert result.sources[1].credibility_score == 0.6
    assert result.sources[2].credibility_score == 0.3


def test_extract_key_points() -> None:
    """Тест извлечения ключевых моментов."""
    synthesizer = ResearchSynthesizer()
    
    sources = [
        Source(
            url="https://example.com",
            title="Example",
            content="Первое предложение для теста. Второе предложение для проверки.",
            credibility_score=0.8,
        ),
    ]
    
    key_points = synthesizer._extract_key_points(sources)
    
    # Должны быть извлечены предложения
    assert len(key_points) > 0
    assert all("Example" in point for point in key_points)


def test_create_synthesis_tool() -> None:
    """Тест создания tool definition."""
    synthesizer = ResearchSynthesizer()
    
    tool = create_synthesis_tool(synthesizer)
    
    assert tool["function"]["name"] == "synthesize_research"
    assert "query" in tool["function"]["parameters"]["required"]
    assert "sources" in tool["function"]["parameters"]["required"]


def test_split_sentences() -> None:
    """Тест разделения текста на предложения."""
    synthesizer = ResearchSynthesizer()
    
    text = "Первое предложение. Второе предложение! Третье?"
    sentences = synthesizer._split_sentences(text)
    
    assert len(sentences) == 3
    assert "Первое предложение" in sentences[0]
    assert "Второе предложение" in sentences[1]
    assert "Третье" in sentences[2]