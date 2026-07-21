# modules/agent/reasoning_demo.py
"""Demo script for Reasoning Loop / ReAct Pattern.

Демонстрирует структуру reasoning loop без реальных вызовов API.
Запуск:
    python -c "from modules.agent.reasoning_demo import main; import asyncio; asyncio.run(main())"
"""

from __future__ import annotations

import asyncio
import logging

from modules.agent.reasoning import (
    ReasoningLoop,
    ReasoningPhase,
    ReasoningState,
    ReasoningStep,
)
from modules.domain.results import ToolResult


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class MockLLM:
    """Мок LLM для демонстрации."""
    
    def __init__(self) -> None:
        self.call_count = 0
    
    async def complete(self, **kwargs) -> "MockResponse":
        self.call_count += 1
        
        # Первый вызов - мысленный процесс
        if self.call_count == 1:
            return MockResponse(
                text="Думаю... для плана по Python нужно собрать информацию. "
                     "<execute_command>{\"command\": \"echo 'Исследую Python темы'\"}</execute_command>",
                tool_calls=[],
            )
        
        # Второй вызов - анализ результатов
        if self.call_count == 2:
            return MockResponse(
                text="Хорошо, теперь составлю структурированный план. "
                     "<read_file>{\"path\": \"/tmp/python_resources.txt\"}</read_file>",
                tool_calls=[],
            )
        
        # Третий вызов - финальный ответ
        return MockResponse(
            text="План по изучению Python для начинающих:\n\n"
                 "1. Установка и настройка\n"
                 "   - Скачать Python с python.org\n"
                 "   - Установить IDE (VS Code/PyCharm)\n"
                 "   - Настроить виртуальное окружение\n\n"
                 "2. Базовый синтаксис\n"
                 "   - Переменные и типы данных\n"
                 "   - Условия и циклы\n"
                 "   - Функции\n\n"
                 "3. Работа с данными\n"
                 "   - Списки, словари, кортежи\n"
                 "   - Строки и регулярные выражения\n"
                 "   - Файлы и исключения\n\n"
                 "4. Объектно-ориентированное программирование\n"
                 "   - Классы и объекты\n"
                 "   - Наследование\n"
                 "   - Магические методы\n\n"
                 "5. Практика\n"
                 "   - Мини-проекты\n"
                 "   - Работа с библиотеками\n"
                 "   - Тестирование",
            tool_calls=[],
        )


class MockResponse:
    """Мок ответа модели."""
    
    def __init__(self, text: str, tool_calls: list) -> None:
        self.text = text
        self.tool_calls = tool_calls


class MockRegistry:
    """Мок реестра инструментов."""
    
    names = ["execute_command", "read_file", "write_file", "list_files"]
    
    def schemas(self):
        return []


class MockRunner:
    """Мок выполнителя инструментов."""
    
    async def execute(self, tool_call, context) -> ToolResult:
        name = tool_call.get("function", {}).get("name", "unknown")
        return ToolResult.ok(f"Выполнен инструмент {name}")


async def main() -> None:
    """Демонстрация Reasoning Loop."""
    # Создаём мок-компоненты
    llm = MockLLM()
    registry = MockRegistry()
    runner = MockRunner()
    
    # Создаём reasoning loop
    loop = ReasoningLoop(
        llm=llm,
        registry=registry,
        runner=runner,
        intent_router=None,
    )
    
    # Пример запроса
    state = ReasoningState(
        turn_id="demo_turn",
        session_id="demo_session",
        original_request="Напиши план по изучению Python для начинающих",
        max_iterations=5,
    )
    
    print("=" * 60)
    print("DEMO: Reasoning Loop / ReAct Pattern")
    print("=" * 60)
    print(f"Запрос: {state.original_request}")
    print(f"Макс итераций: {state.max_iterations}")
    print("=" * 60)
    
    # Запускаем цикл
    response = await loop.run(state)
    
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ВЫПОЛНЕНИЯ")
    print("=" * 60)
    print(f"Итераций выполнено: {state.current_iteration}")
    print(f"Цель достигнута: {state.goal_achieved}")
    
    print("\n" + "-" * 60)
    print("ШАГИ REASONING:")
    print("-" * 60)
    
    for i, step in enumerate(state.steps, 1):
        print(f"\n{i}. {step.phase.value.upper()}")
        print(f"   Confidence: {step.confidence:.2%}")
        if step.tool_calls:
            print(f"   Tool calls: {len(step.tool_calls)}")
            for tc in step.tool_calls:
                tool_name = tc.get("function", {}).get("name", "unknown")
                print(f"      - {tool_name}")
        if step.tool_results:
            print(f"   Tool results: {len(step.tool_results)}")
            for result in step.tool_results:
                success = result.get("result", {}).get("success", False)
                status = "✓" if success else "✗"
                name = result.get("name", "unknown")
                print(f"      {status} {name}")
    
    print("\n" + "-" * 60)
    print("ФИНАЛЬНЫЙ ОТВЕТ:")
    print("-" * 60)
    print(response.display_text)


if __name__ == "__main__":
    asyncio.run(main())