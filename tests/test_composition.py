# tests/test_composition.py
from __future__ import annotations

import asyncio

from modules.tools.composition import (
    ToolChain,
    ToolChainStep,
    ToolComposer,
    create_research_chain,
    create_obsidian_workflow,
)
from modules.domain.results import ToolResult


def test_tool_chain_step_creation() -> None:
    """Тест создания шага цепочки."""
    step = ToolChainStep(
        name="test_tool",
        arguments={"arg1": "value1"},
    )
    
    assert step.name == "test_tool"
    assert step.arguments == {"arg1": "value1"}
    assert step.condition is None
    assert step.continue_on_failure is False


def test_tool_chain_step_with_condition() -> None:
    """Тест создания шага с условием."""
    step = ToolChainStep(
        name="conditional_tool",
        arguments={},
        condition="success_count > 3",
    )
    
    assert step.condition == "success_count > 3"


def test_tool_chain_creation() -> None:
    """Тест создания цепочки."""
    chain = ToolChain()
    
    assert chain.steps == []
    assert chain.parallel is False


def test_tool_chain_add_step() -> None:
    """Тест добавления шагов в цепочку."""
    chain = ToolChain()
    
    chain.add_step("tool1", {"arg": "value1"})
    chain.add_step("tool2", {"arg": "value2"}, condition="tool1.success")
    
    assert len(chain.steps) == 2
    assert chain.steps[0].name == "tool1"
    assert chain.steps[1].condition == "tool1.success"


def test_tool_chain_to_tool_calls() -> None:
    """Тест преобразования цепочки в tool calls."""
    chain = ToolChain()
    chain.add_step("write_in_application", {
        "app_name": "Obsidian",
        "text": "Hello",
    })
    
    tool_calls = chain.to_tool_calls()
    
    assert len(tool_calls) == 1
    assert tool_calls[0]["function"]["name"] == "write_in_application"


def test_tool_chain_to_tool_calls_with_condition() -> None:
    """Тест фильтрации tool calls по условию."""
    chain = ToolChain()
    chain.add_step("tool1", {}, condition="skip_this")
    chain.add_step("tool2", {})
    
    # Если условие не выполняется - инструмент пропускается
    tool_calls = chain.to_tool_calls({"skip_this": False})
    
    assert len(tool_calls) == 1
    assert tool_calls[0]["function"]["name"] == "tool2"


def test_tool_composer_creation() -> None:
    """Тест создания композитора."""
    class MockRunner:
        pass
    
    composer = ToolComposer(MockRunner())
    
    assert composer.runner is not None


def test_tool_composer_sequential_execution() -> None:
    """Тест последовательного выполнения цепочки."""
    class MockRunner:
        executed_calls = []
        
        async def execute(self, tool_call, context):
            name = tool_call.get("function", {}).get("name")
            self.executed_calls.append(name)
            return ToolResult.ok(f"Executed {name}")
    
    async def run_test():
        runner = MockRunner()
        composer = ToolComposer(runner)
        
        chain = ToolChain()
        chain.add_step("tool1", {})
        chain.add_step("tool2", {})
        
        results = await composer.execute_chain(
            chain,
            session_id="test_session",
            turn_id="test_turn",
        )
        
        assert len(results) == 2
        assert runner.executed_calls == ["tool1", "tool2"]
        assert all(r.success for r in results)
    
    asyncio.run(run_test())


def test_tool_composer_parallel_execution() -> None:
    """Тест параллельного выполнения цепочки."""
    class MockRunner:
        call_times = []
        
        async def execute(self, tool_call, context):
            import time
            name = tool_call.get("function", {}).get("name")
            # Имитируем разное время выполнения
            await asyncio.sleep(0.01 if name == "fast_tool" else 0.03)
            self.call_times.append(time.time())
            return ToolResult.ok(f"Executed {name}")
    
    async def run_test():
        import time
        runner = MockRunner()
        composer = ToolComposer(runner)
        
        chain = ToolChain(parallel=True)
        chain.add_step("fast_tool", {})
        chain.add_step("slow_tool", {})
        
        start = time.time()
        results = await composer.execute_chain(
            chain,
            session_id="test_session",
            turn_id="test_turn",
        )
        elapsed = time.time() - start
        
        assert len(results) == 2
        # Параллельное выполнение должно занять примерно столько же, сколько slowest tool
        # а не сумму времени всех инструментов
        assert elapsed < 0.1  # Должно быть быстрее 0.1s (0.03 + 0.03 = 0.06 sequential)
        assert all(r.success for r in results)
    
    asyncio.run(run_test())


def test_tool_composer_stops_on_failure() -> None:
    """Тест остановки цепочки при ошибке."""
    class MockRunner:
        def __init__(self):
            self.call_count = 0
        
        async def execute(self, tool_call, context):
            self.call_count += 1
            name = tool_call.get("function", {}).get("name")
            
            if self.call_count == 1:
                return ToolResult.ok("First succeeded")
            return ToolResult.failure("SECOND_FAILED", "Second failed")
    
    async def run_test():
        runner = MockRunner()
        composer = ToolComposer(runner)
        
        chain = ToolChain()
        chain.add_step("tool1", {})
        chain.add_step("tool2", {})
        chain.add_step("tool3", {})  # Этот не должен выполниться
        
        results = await composer.execute_chain(
            chain,
            session_id="test_session",
            turn_id="test_turn",
        )
        
        assert len(results) == 2  # Только 2 инструмента выполнились
        assert runner.call_count == 2
    
    asyncio.run(run_test())


def test_tool_composer_continue_on_failure() -> None:
    """Тест продолжения цепочки при ошибке с флагом continue_on_failure."""
    class MockRunner:
        call_results = ["ok", "fail", "ok"]
        call_count = 0
        
        async def execute(self, tool_call, context):
            self.call_count += 1
            result = self.call_results[self.call_count - 1]
            
            if result == "ok":
                return ToolResult.ok(f"Step {self.call_count}")
            return ToolResult.failure("FAILED", f"Step {self.call_count} failed")
    
    async def run_test():
        runner = MockRunner()
        composer = ToolComposer(runner)
        
        chain = ToolChain()
        chain.add_step("tool1", {})
        chain.add_step("tool2", {}, continue_on_failure=True)
        chain.add_step("tool3", {})
        
        results = await composer.execute_chain(
            chain,
            session_id="test_session",
            turn_id="test_turn",
        )
        
        assert len(results) == 3  # Все 3 инструмента выполнились
        assert runner.call_count == 3
    
    asyncio.run(run_test())


def test_create_research_chain() -> None:
    """Тест создания цепочки исследования."""
    chain = create_research_chain("test query", max_sources=3)
    
    assert len(chain.steps) == 1
    assert chain.steps[0].name == "browser_research"
    assert chain.steps[0].arguments["query"] == "test query"


def test_create_obsidian_workflow() -> None:
    """Тест создания цепочки для Obsidian."""
    chain = create_obsidian_workflow(
        action="create",
        content="Test content",
        title="Test Note",
    )
    
    assert len(chain.steps) == 2
    assert chain.steps[0].name == "open_and_focus"
    assert chain.steps[1].name == "create_obsidian_note"