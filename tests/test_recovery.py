# tests/test_recovery.py
from __future__ import annotations

import asyncio

from modules.agent.recovery import (
    RecoveryAction,
    RecoveryContext,
    RecoveryEngine,
)
from modules.domain.results import ToolResult


def test_success_continues() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        ToolResult.ok("Готово."),
        RecoveryContext(
            operation_name="test",
        ),
    )

    assert decision.action == RecoveryAction.CONTINUE


def test_policy_denial_is_not_retried() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        ToolResult.failure(
            "POLICY_DENIED",
            "Запрещено.",
        ),
        RecoveryContext(
            operation_name="dangerous",
        ),
    )

    assert decision.action == RecoveryAction.ABORT


def test_retryable_error_is_retried() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        ToolResult.failure(
            "TOOL_TIMEOUT",
            "Timeout.",
            retryable=True,
        ),
        RecoveryContext(
            operation_name="temporary",
            attempt=1,
            max_attempts=3,
        ),
    )

    assert decision.action == RecoveryAction.RETRY
    assert decision.delay_seconds > 0


def test_retry_stops_at_max_attempts() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        ToolResult.failure(
            "TOOL_TIMEOUT",
            "Timeout.",
            retryable=True,
        ),
        RecoveryContext(
            operation_name="temporary",
            attempt=3,
            max_attempts=3,
        ),
    )

    assert decision.action == RecoveryAction.ABORT


def test_missing_input_asks_user() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        ToolResult.failure(
            "EMPTY_TEXT",
            "Текст не указан.",
        ),
        RecoveryContext(
            operation_name="write",
        ),
    )

    assert decision.action == RecoveryAction.ASK_USER
    assert decision.requires_user_input


def test_fallback_is_selected() -> None:
    engine = RecoveryEngine()

    decision = engine.decide(
        ToolResult.failure(
            "ELEMENT_NOT_FOUND",
            "Элемент не найден.",
        ),
        RecoveryContext(
            operation_name="click",
            has_fallback=True,
        ),
    )

    assert decision.action == RecoveryAction.FALLBACK


def test_cancellation_prevents_execution() -> None:
    async def scenario() -> None:
        engine = RecoveryEngine()
        event = asyncio.Event()
        event.set()

        called = False

        async def operation(
            attempt: int,
        ) -> ToolResult:
            nonlocal called
            called = True
            return ToolResult.ok("Не должно выполниться.")

        result, decision = (
            await engine.execute_with_recovery(
                operation,
                operation_name="cancelled",
                cancellation_event=event,
            )
        )

        assert not result.success
        assert result.code == "TOOL_CANCELLED"
        assert not called
        assert decision.action == RecoveryAction.ABORT

    asyncio.run(scenario())
