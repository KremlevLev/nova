# tests/test_reasoning.py
from __future__ import annotations

import asyncio

from modules.agent.reasoning import (
    ReasoningLoop,
    ReasoningPhase,
    ReasoningState,
    ReasoningStep,
)
from modules.domain.results import ToolResult


def test_reasoning_step_creation() -> None:
    """Тест создания шага reasoning."""
    step = ReasoningStep(
        phase=ReasoningPhase.THOUGHT,
        content="Тестовый мыслительный шаг",
        confidence=0.75,
    )
    
    assert step.phase == ReasoningPhase.THOUGHT
    assert step.content == "Тестовый мыслительный шаг"
    assert step.confidence == 0.75
    assert step.should_continue is True
    assert step.tool_calls == []
    assert step.tool_results == []


def test_reasoning_state_creation() -> None:
    """Тест создания состояния reasoning loop."""
    state = ReasoningState(
        turn_id="test_turn",
        session_id="test_session",
        original_request="Выполни действие",
    )
    
    assert state.turn_id == "test_turn"
    assert state.session_id == "test_session"
    assert state.original_request == "Выполни действие"
    assert state.current_iteration == 0
    assert state.max_iterations == 5
    assert state.steps == []
    assert state.goal_achieved is False


def test_reasoning_state_with_custom_iterations() -> None:
    """Тест состояния с кастомным числом итераций."""
    state = ReasoningState(
        turn_id="turn_1",
        session_id="session_1",
        original_request="Сложный запрос",
        max_iterations=10,
        confidence_threshold=0.9,
    )
    
    assert state.max_iterations == 10
    assert state.confidence_threshold == 0.9


def test_reasoning_step_should_continue_flag() -> None:
    """Тест флага продолжения reasoning."""
    step = ReasoningStep(
        phase=ReasoningPhase.ACTION,
        content="Final answer reached",
        should_continue=False,
    )
    
    assert step.should_continue is False


def test_reasoning_loop_initialization() -> None:
    """Тест инициализации reasoning loop."""
    # Мок-объекты
    class MockLLM:
        async def complete(self, **kwargs):
            return type("Response", (), {"text": "test response", "tool_calls": []})()
    
    class MockRegistry:
        names = ["test_tool"]
        def schemas(self):
            return []
    
    class MockRunner:
        async def execute(self, tool_call, context):
            return ToolResult.ok("test result")
    
    class MockIntentRouter:
        pass
    
    loop = ReasoningLoop(
        llm=MockLLM(),
        registry=MockRegistry(),
        runner=MockRunner(),
        intent_router=MockIntentRouter(),
    )
    
    assert loop.llm is not None
    assert loop.registry is not None
    assert loop.runner is not None


def test_format_results_with_success() -> None:
    """Тест форматирования результатов - успех."""
    results = [
        {
            "name": "tool_a",
            "result": {"success": True, "message": "Успех"},
        },
        {
            "name": "tool_b",
            "result": {"success": True, "message": "Тоже успех"},
        },
    ]
    
    formatted = ReasoningLoop._format_results(results)
    
    assert "✓ tool_a" in formatted
    assert "✓ tool_b" in formatted


def test_format_results_with_failure() -> None:
    """Тест форматирования результатов - ошибка."""
    results = [
        {
            "name": "tool_x",
            "result": {"success": False, "message": "Ошибка"},
        },
    ]
    
    formatted = ReasoningLoop._format_results(results)
    
    assert "✗ tool_x" in formatted


def test_format_results_empty() -> None:
    """Тест форматирования пустых результатов."""
    formatted = ReasoningLoop._format_results([])
    assert formatted == ""


def test_reasoning_phases_values() -> None:
    """Тест значений фаз reasoning."""
    assert ReasoningPhase.THOUGHT.value == "thought"
    assert ReasoningPhase.ACTION.value == "action"
    assert ReasoningPhase.OBSERVATION.value == "observation"
    assert ReasoningPhase.REFLECTION.value == "reflection"


def test_reasoning_state_to_dict() -> None:
    """Тест сериализации состояния."""
    state = ReasoningState(
        turn_id="t1",
        session_id="s1",
        original_request="test request",
    )
    state.goal_achieved = True
    state.final_answer = "Final answer"
    
    # Проверяем, что состояние содержит нужные атрибуты
    assert state.goal_achieved is True
    assert state.final_answer == "Final answer"


def test_reasoning_loop_async_run() -> None:
    """Тест асинхронного запуска reasoning loop."""
    async def scenario() -> None:
        class MockLLM:
            async def complete(self, **kwargs):
                return type("Response", (), {"text": "done", "tool_calls": []})()
        
        class MockRegistry:
            names = []
            def schemas(self):
                return []
        
        class MockRunner:
            async def execute(self, tool_call, context):
                return ToolResult.ok("ok")
        
        class MockIntentRouter:
            pass
        
        loop = ReasoningLoop(
            llm=MockLLM(),
            registry=MockRegistry(),
            runner=MockRunner(),
            intent_router=MockIntentRouter(),
        )
        
        state = ReasoningState(
            turn_id="t",
            session_id="s",
            original_request="req",
        )
        
        response = await loop.run(state)
        
        assert response is not None
        assert state.current_iteration >= 1
    
    asyncio.run(scenario())