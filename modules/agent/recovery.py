# modules/agent/recovery.py
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Awaitable, Callable

from modules.domain.results import ToolResult


logger = logging.getLogger("RecoveryEngine")


class RecoveryAction(StrEnum):
    RETRY = "retry"
    FALLBACK = "fallback"
    ASK_USER = "ask_user"
    ROLLBACK = "rollback"
    ABORT = "abort"
    CONTINUE = "continue"


@dataclass(slots=True)
class RecoveryDecision:
    action: RecoveryAction
    reason: str

    delay_seconds: float = 0.0
    max_attempts: int = 1

    requires_user_input: bool = False
    should_rollback: bool = False


@dataclass(slots=True)
class RecoveryContext:
    operation_name: str
    attempt: int = 1
    max_attempts: int = 3

    has_fallback: bool = False
    has_rollback: bool = False

    user_denied: bool = False
    cancellation_requested: bool = False


class RecoveryEngine:
    """
    Выбирает стратегию восстановления после ошибки инструмента.

    Recovery Engine не повторяет действие самостоятельно без проверки:
    - идемпотентности;
    - лимита попыток;
    - типа ошибки;
    - решения пользователя;
    - наличия rollback.
    """

    NON_RETRYABLE_CODES = frozenset(
        {
            "POLICY_DENIED",
            "USER_DENIED",
            "TOOL_CANCELLED",
            "ARGUMENT_VALIDATION_FAILED",
            "INVALID_ARGUMENTS_JSON",
            "INVALID_ARGUMENTS_TYPE",
            "TOOL_NOT_FOUND",
            "INVALID_TOOL_CALL",
            "INVALID_TOOL_NAME",
            "APPLICATION_NOT_FOUND",
            "EMPTY_TEXT",
            "EMPTY_APPLICATION_NAME",
        }
    )

    USER_INPUT_CODES = frozenset(
        {
            "EMPTY_TEXT",
            "EMPTY_APPLICATION_NAME",
            "MISSING_REQUIRED_CONTEXT",
            "AMBIGUOUS_TARGET",
            "ACTIVE_WINDOW_CHANGED",
        }
    )

    FALLBACK_CODES = frozenset(
        {
            "UI_AUTOMATION_NOT_AVAILABLE",
            "ELEMENT_NOT_FOUND",
            "OCR_ENGINE_NOT_AVAILABLE",
            "PLAYWRIGHT_NOT_INSTALLED",
            "BROWSER_START_FAILED",
            "MODEL_ROUTE_FAILED",
        }
    )

    RETRYABLE_CODES = frozenset(
        {
            "TOOL_TIMEOUT",
            "PROCESS_START_FAILED",
            "BROWSER_NAVIGATION_FAILED",
            "BROWSER_TEXT_READ_FAILED",
            "BROWSER_CLICK_FAILED",
            "BROWSER_FILL_FAILED",
            "UI_AUTOMATION_ERROR",
            "CONNECTION_ERROR",
            "TEMPORARY_FAILURE",
        }
    )

    def decide(
        self,
        result: ToolResult,
        context: RecoveryContext,
    ) -> RecoveryDecision:
        if result.success:
            return RecoveryDecision(
                action=RecoveryAction.CONTINUE,
                reason="Операция завершена успешно.",
            )

        if context.cancellation_requested:
            return RecoveryDecision(
                action=RecoveryAction.ABORT,
                reason="Операция отменена пользователем.",
            )

        if context.user_denied:
            return RecoveryDecision(
                action=RecoveryAction.ABORT,
                reason=(
                    "Пользователь запретил выполнение. "
                    "Автоматический повтор запрещён."
                ),
            )

        if result.code in self.USER_INPUT_CODES:
            return RecoveryDecision(
                action=RecoveryAction.ASK_USER,
                reason=result.message,
                requires_user_input=True,
            )

        if result.code in self.NON_RETRYABLE_CODES:
            return RecoveryDecision(
                action=RecoveryAction.ABORT,
                reason=(
                    "Ошибка не допускает автоматический повтор: "
                    + result.message
                ),
            )

        if (
            result.code in self.FALLBACK_CODES
            and context.has_fallback
        ):
            return RecoveryDecision(
                action=RecoveryAction.FALLBACK,
                reason=(
                    "Основной способ не сработал, "
                    "доступен резервный механизм."
                ),
            )

        may_retry = (
            result.retryable
            or result.code in self.RETRYABLE_CODES
        )

        if (
            may_retry
            and context.attempt < context.max_attempts
        ):
            delay = min(
                2 ** max(0, context.attempt - 1),
                8,
            )

            return RecoveryDecision(
                action=RecoveryAction.RETRY,
                reason=(
                    f"Временная ошибка. Попытка "
                    f"{context.attempt + 1} из "
                    f"{context.max_attempts}."
                ),
                delay_seconds=float(delay),
                max_attempts=context.max_attempts,
            )

        if (
            context.has_rollback
            and result.rollback_token
        ):
            return RecoveryDecision(
                action=RecoveryAction.ROLLBACK,
                reason=(
                    "Операция завершилась ошибкой, "
                    "доступен откат."
                ),
                should_rollback=True,
            )

        return RecoveryDecision(
            action=RecoveryAction.ABORT,
            reason=(
                "Безопасная стратегия восстановления "
                "не найдена."
            ),
        )

    async def execute_with_recovery(
        self,
        operation: Callable[
            [int],
            Awaitable[ToolResult],
        ],
        *,
        operation_name: str,
        max_attempts: int = 3,
        has_fallback: bool = False,
        has_rollback: bool = False,
        cancellation_event: asyncio.Event | None = None,
    ) -> tuple[ToolResult, RecoveryDecision]:
        """
        Выполняет только безопасные автоматические повторы.

        Fallback, ASK_USER и ROLLBACK возвращаются вызывающему коду:
        конкретный механизм выбирает application layer.
        """
        last_result = ToolResult.failure(
            "OPERATION_NOT_STARTED",
            "Операция не была запущена.",
        )

        for attempt in range(1, max_attempts + 1):
            if (
                cancellation_event is not None
                and cancellation_event.is_set()
            ):
                cancelled_result = ToolResult.failure(
                    "TOOL_CANCELLED",
                    (
                        f"Операция '{operation_name}' "
                        "отменена."
                    ),
                )

                decision = RecoveryDecision(
                    action=RecoveryAction.ABORT,
                    reason="Операция отменена.",
                )

                return cancelled_result, decision

            try:
                last_result = await operation(attempt)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(
                    "Необработанная ошибка операции %s.",
                    operation_name,
                )

                last_result = ToolResult.failure(
                    "UNHANDLED_OPERATION_ERROR",
                    (
                        f"Необработанная ошибка "
                        f"'{operation_name}': {exc}"
                    ),
                    retryable=True,
                )

            context = RecoveryContext(
                operation_name=operation_name,
                attempt=attempt,
                max_attempts=max_attempts,
                has_fallback=has_fallback,
                has_rollback=has_rollback,
                cancellation_requested=(
                    cancellation_event is not None
                    and cancellation_event.is_set()
                ),
            )

            decision = self.decide(
                last_result,
                context,
            )

            logger.info(
                (
                    "Recovery decision: operation=%s "
                    "attempt=%s action=%s code=%s"
                ),
                operation_name,
                attempt,
                decision.action.value,
                last_result.code,
            )

            if decision.action == RecoveryAction.CONTINUE:
                return last_result, decision

            if decision.action != RecoveryAction.RETRY:
                return last_result, decision

            if decision.delay_seconds > 0:
                try:
                    if cancellation_event is None:
                        await asyncio.sleep(
                            decision.delay_seconds
                        )
                    else:
                        await asyncio.wait_for(
                            cancellation_event.wait(),
                            timeout=decision.delay_seconds,
                        )

                        cancelled_result = ToolResult.failure(
                            "TOOL_CANCELLED",
                            (
                                f"Операция '{operation_name}' "
                                "отменена во время ожидания."
                            ),
                        )

                        return (
                            cancelled_result,
                            RecoveryDecision(
                                action=RecoveryAction.ABORT,
                                reason="Операция отменена.",
                            ),
                        )

                except asyncio.TimeoutError:
                    pass

        final_decision = self.decide(
            last_result,
            RecoveryContext(
                operation_name=operation_name,
                attempt=max_attempts,
                max_attempts=max_attempts,
                has_fallback=has_fallback,
                has_rollback=has_rollback,
            ),
        )

        return last_result, final_decision
