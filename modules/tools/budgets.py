# modules/tools/budgets.py
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field


logger = logging.getLogger("Budgets")


@dataclass(slots=True)
class AgentBudget:
    """
    Бюджет одного пользовательского запроса.

    После исчерпания любого лимита агент должен остановиться
    и сформировать итог по уже выполненным инструментам.
    """

    max_model_calls: int = 8
    max_tool_calls: int = 12
    max_wall_time_seconds: float = 120.0
    max_same_tool_repeats: int = 1

    # Для будущего использования.
    max_tokens: int = 0
    max_cost: float = 0.0


@dataclass(slots=True)
class BudgetState:
    """
    Текущее состояние бюджета для одного запроса.
    """

    model_calls_used: int = 0
    tool_calls_used: int = 0
    started_at: float = field(
        default_factory=time.monotonic
    )

    tool_call_signatures: dict[str, int] = field(
        default_factory=dict
    )

    def elapsed_seconds(self) -> float:
        return (
            time.monotonic() - self.started_at
        )

    def record_model_call(self) -> None:
        self.model_calls_used += 1

    def record_tool_call(
        self,
        signature: str,
    ) -> None:
        self.tool_calls_used += 1
        self.tool_call_signatures[signature] = (
            self.tool_call_signatures.get(
                signature,
                0
            )
            + 1
        )

    def is_exhausted(
        self,
        budget: AgentBudget,
    ) -> tuple[bool, str | None]:
        if (
            self.model_calls_used
            >= budget.max_model_calls
        ):
            return (
                True,
                (
                    f"Достигнут лимит модельных вызовов: "
                    f"{self.model_calls_used}/"
                    f"{budget.max_model_calls}"
                ),
            )

        if (
            self.tool_calls_used
            >= budget.max_tool_calls
        ):
            return (
                True,
                (
                    f"Достигнут лимит инструментов: "
                    f"{self.tool_calls_used}/"
                    f"{budget.max_tool_calls}"
                ),
            )

        elapsed = self.elapsed_seconds()

        if (
            elapsed
            >= budget.max_wall_time_seconds
        ):
            return (
                True,
                (
                    f"Достигнут лимит времени: "
                    f"{elapsed:.0f}/"
                    f"{budget.max_wall_time_seconds:.0f} сек."
                ),
            )

        return (False, None)

    def is_tool_repeated(
        self,
        signature: str,
        budget: AgentBudget,
    ) -> bool:
        current_count = (
            self.tool_call_signatures.get(
                signature,
                0
            )
        )

        return (
            current_count
            >= budget.max_same_tool_repeats
        )


class BudgetManager:
    """
    Управляет бюджетами для каждого пользовательского запроса.
    """

    def __init__(self) -> None:
        self._states: dict[
            str,
            BudgetState,
        ] = {}
        self._lock = threading.RLock()
        self.default_budget = AgentBudget()

    def create_state(
        self,
        turn_id: str,
        *,
        budget: AgentBudget | None = None,
    ) -> BudgetState:
        with self._lock:
            state = BudgetState()
            self._states[turn_id] = state

        return state

    def get_state(
        self,
        turn_id: str,
    ) -> BudgetState | None:
        with self._lock:
            return self._states.get(turn_id)

    def remove_state(
        self,
        turn_id: str,
    ) -> None:
        with self._lock:
            self._states.pop(turn_id, None)

    def record_model_call(
        self,
        turn_id: str,
    ) -> None:
        state = self.get_state(turn_id)

        if state is not None:
            state.record_model_call()

    def record_tool_call(
        self,
        turn_id: str,
        signature: str,
    ) -> None:
        state = self.get_state(turn_id)

        if state is not None:
            state.record_tool_call(signature)

    def is_exhausted(
        self,
        turn_id: str,
        *,
        budget: AgentBudget | None = None,
    ) -> tuple[bool, str | None]:
        state = self.get_state(turn_id)

        if state is None:
            return (False, None)

        return state.is_exhausted(
            budget or self.default_budget
        )

    def is_tool_repeated(
        self,
        turn_id: str,
        signature: str,
        *,
        budget: AgentBudget | None = None,
    ) -> bool:
        state = self.get_state(turn_id)

        if state is None:
            return False

        return state.is_tool_repeated(
            signature,
            budget or self.default_budget,
        )
