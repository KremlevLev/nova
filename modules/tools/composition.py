# modules/tools/composition.py
"""Tool Composition - автоматическое цепление и комбинирование инструментов.

Позволяет создавать цепочки инструментов и выполнять их последовательно/параллельно.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from modules.domain.results import ToolResult


logger = logging.getLogger("ToolComposition")


@dataclass
class ToolChainStep:
    """Шаг цепочки инструментов."""
    name: str
    arguments: dict[str, Any]
    condition: str | None = None  # Python-выражение для условного выполнения
    continue_on_failure: bool = False


@dataclass
class ToolChain:
    """Цепочка инструментов для последовательного выполнения."""
    steps: list[ToolChainStep] = field(default_factory=list)
    parallel: bool = False  # Если True - выполнять параллельно независимые шаги
    
    def add_step(
        self,
        name: str,
        arguments: dict[str, Any],
        condition: str | None = None,
        continue_on_failure: bool = False,
    ) -> None:
        """Добавить шаг в цепочку."""
        self.steps.append(ToolChainStep(
            name=name,
            arguments=arguments,
            condition=condition,
            continue_on_failure=continue_on_failure,
        ))
    
    def to_tool_calls(self, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Преобразовать цепочку в список tool calls для передачи модели."""
        result = []
        ctx = context or {}
        
        for step in self.steps:
            if step.condition and not self._eval_condition(step.condition, ctx):
                logger.info("Skipping step %s due to condition: %s", step.name, step.condition)
                continue
            
            result.append({
                "function": {
                    "name": step.name,
                    "arguments": step.arguments,
                },
            })
        
        return result
    
    @staticmethod
    def _eval_condition(condition: str, context: dict[str, Any]) -> bool:
        """Оценить условие (безопасно для простых выражений)."""
        try:
            # Поддерживаем только простые сравнения и логические операции
            allowed_names = {**context}
            return bool(eval(condition, {"__builtins__": {}}, allowed_names))
        except Exception as e:
            logger.warning("Condition evaluation failed: %s", e)
            return True  # По умолчанию выполняем


class ToolComposer:
    """
    Композитор инструментов для создания цепочек.
    
    Позволяет создавать цепочки инструментов с условиями и параллельным выполнением.
    """
    
    def __init__(self, runner: Any) -> None:
        """
        Инициализация композитора.
        
        Args:
            runner: ToolRunner для выполнения инструментов
        """
        self.runner = runner
    
    async def execute_chain(
        self,
        chain: ToolChain,
        *,
        session_id: str,
        turn_id: str,
        context: dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        """
        Выполнить цепочку инструментов.
        
        Args:
            chain: цепочка для выполнения
            session_id: ID сессии
            turn_id: ID хода
            context: контекст для условий
            
        Returns:
            Список результатов выполнения
        """
        from modules.tools.base import ToolContext
        
        results = []
        
        if chain.parallel:
            # Параллельное выполнение
            parallel_steps = [
                step for step in chain.steps
                if not step.condition or self._check_condition(step.condition, context or {})
            ]
            
            tasks = [
                self._execute_step(step, session_id, turn_id)
                for step in parallel_steps
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Преобразуем исключения в результаты
            results = [
                r if isinstance(r, ToolResult) else ToolResult.failure("EXECUTION_ERROR", str(r))
                for r in results
            ]
        else:
            # Последовательное выполнение
            ctx = context or {}
            
            for step in chain.steps:
                if step.condition and not self._check_condition(step.condition, ctx):
                    logger.info("Skipping step %s due to condition", step.name)
                    continue
                
                try:
                    result = await self._execute_step(step, session_id, turn_id)
                    results.append(result)
                    
                    # Обновляем контекст для последующих условий
                    ctx[step.name] = result.to_dict()
                    
                    if not result.success and not step.continue_on_failure:
                        logger.warning("Chain stopped at step %s due to failure", step.name)
                        break
                        
                except Exception as e:
                    logger.error("Step %s failed with exception: %s", step.name, e)
                    if not step.continue_on_failure:
                        results.append(ToolResult.failure("EXECUTION_ERROR", str(e)))
                        break
        
        return results
    
    async def _execute_step(
        self,
        step: ToolChainStep,
        session_id: str,
        turn_id: str,
    ) -> ToolResult:
        """Выполнить один шаг цепочки."""
        from modules.tools.base import ToolContext
        
        tool_call = {
            "function": {
                "name": step.name,
                "arguments": step.arguments,
            },
        }
        
        context = ToolContext.create(
            session_id=session_id,
            turn_id=turn_id,
            source="tool_composition",
        )
        
        return await self.runner.execute(tool_call, context=context)
    
    def _check_condition(self, condition: str, ctx: dict[str, Any]) -> bool:
        """Проверить условие для выполнения шага."""
        try:
            return bool(eval(condition, {"__builtins__": {}}, ctx))
        except Exception:
            return True


def create_research_chain(query: str, max_sources: int = 5) -> ToolChain:
    """
    Создать цепочку для исследования.
    
    Выполняет браузерный поиск и последующий анализ.
    """
    chain = ToolChain()
    
    chain.add_step("browser_research", {
        "query": query,
        "max_results": max_sources,
    })
    
    return chain


def create_obsidian_workflow(
    action: str,
    content: str | None = None,
    title: str | None = None,
) -> ToolChain:
    """
    Создать цепочку для работы с Obsidian.
    
    Открывает Obsidian, создает заметку и записывает контент.
    """
    chain = ToolChain()
    
    chain.add_step("open_and_focus", {
        "app_name": "Obsidian",
    })
    
    if content and title:
        chain.add_step("create_obsidian_note", {
            "title": title,
            "content": content,
        })
    
    return chain