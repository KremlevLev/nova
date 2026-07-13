# tests/test_planning.py
from __future__ import annotations

import asyncio

from modules.agent.planning import (
    ExecutionPlan,
    PlanBudget,
    PlanExecutor,
    PlanStep,
    PlanStepStatus,
    PlanValidator,
)
from modules.domain.results import (
    ToolResult,
    VerificationResult,
)
from modules.tools.base import (
    RiskLevel,
    ToolCategory,
    ToolDefinition,
)
from modules.tools.runtime import (
    ToolRegistry,
    ToolRunner,
)


def create_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register_definition(
        ToolDefinition(
            name="echo",
            description="Возвращает текст.",
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                },
                "required": ["text"],
            },
            handler=lambda text: ToolResult.ok(
                text,
                data={"text": text},
                verification=VerificationResult(
                    verified=True,
                    method="echo",
                    confidence=1.0,
                ),
            ),
            category=ToolCategory.SYSTEM_READ,
            risk=RiskLevel.READ_ONLY,
            idempotent=True,
        )
    )

    registry.register_definition(
        ToolDefinition(
            name="fail",
            description="Всегда завершается ошибкой.",
            parameters={
                "type": "object",
                "properties": {},
            },
            handler=lambda: ToolResult.failure(
                "TEST_FAILURE",
                "Тестовая ошибка.",
            ),
            category=ToolCategory.SYSTEM_READ,
            risk=RiskLevel.READ_ONLY,
        )
    )

    return registry


def test_valid_plan() -> None:
    registry = create_registry()

    plan = ExecutionPlan(
        goal="Выполнить два шага",
        steps=[
            PlanStep(
                step_id="one",
                tool_name="echo",
                arguments={"text": "one"},
            ),
            PlanStep(
                step_id="two",
                tool_name="echo",
                arguments={"text": "two"},
                depends_on=["one"],
            ),
        ],
    )

    validation = PlanValidator.validate(
        plan,
        registry,
    )

    assert validation.valid
    assert not validation.errors


def test_unknown_tool_is_rejected() -> None:
    registry = create_registry()

    plan = ExecutionPlan(
        goal="Тест",
        steps=[
            PlanStep(
                step_id="one",
                tool_name="unknown",
                arguments={},
            ),
        ],
    )

    validation = PlanValidator.validate(
        plan,
        registry,
    )

    assert not validation.valid
    assert any(
        "не зарегистрирован" in error
        for error in validation.errors
    )


def test_cycle_is_rejected() -> None:
    registry = create_registry()

    plan = ExecutionPlan(
        goal="Циклический тест",
        steps=[
            PlanStep(
                step_id="one",
                tool_name="echo",
                arguments={"text": "one"},
                depends_on=["two"],
            ),
            PlanStep(
                step_id="two",
                tool_name="echo",
                arguments={"text": "two"},
                depends_on=["one"],
            ),
        ],
    )

    validation = PlanValidator.validate(
        plan,
        registry,
    )

    assert not validation.valid
    assert any(
        "циклические" in error
        for error in validation.errors
    )


def test_plan_executes_in_dependency_order() -> None:
    async def scenario() -> None:
        order: list[str] = []

        registry = ToolRegistry()

        def record(text: str) -> ToolResult:
            order.append(text)

            return ToolResult.ok(
                text,
                verification=VerificationResult(
                    verified=True,
                    method="test",
                    confidence=1.0,
                ),
            )

        registry.register_definition(
            ToolDefinition(
                name="record",
                description="Записывает порядок.",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                        },
                    },
                    "required": ["text"],
                },
                handler=record,
                category=ToolCategory.SYSTEM_READ,
                risk=RiskLevel.READ_ONLY,
            )
        )

        executor = PlanExecutor(
            registry=registry,
            runner=ToolRunner(registry),
        )

        plan = ExecutionPlan(
            goal="Проверить порядок",
            steps=[
                PlanStep(
                    step_id="first",
                    tool_name="record",
                    arguments={"text": "first"},
                ),
                PlanStep(
                    step_id="second",
                    tool_name="record",
                    arguments={"text": "second"},
                    depends_on=["first"],
                ),
            ],
        )

        result = await executor.execute(
            plan,
            session_id="session-test",
            turn_id="turn-test",
        )

        assert result.success
        assert order == ["first", "second"]
        assert result.completed_steps == 2

    asyncio.run(scenario())


def test_critical_failure_stops_plan() -> None:
    async def scenario() -> None:
        registry = create_registry()

        executor = PlanExecutor(
            registry=registry,
            runner=ToolRunner(registry),
        )

        plan = ExecutionPlan(
            goal="Проверить остановку",
            steps=[
                PlanStep(
                    step_id="fail-step",
                    tool_name="fail",
                    arguments={},
                    critical=True,
                ),
                PlanStep(
                    step_id="dependent",
                    tool_name="echo",
                    arguments={"text": "never"},
                    depends_on=["fail-step"],
                ),
            ],
        )

        result = await executor.execute(
            plan,
            session_id="session-test",
            turn_id="turn-test",
        )

        assert not result.success
        assert result.failed_steps == 1
        assert (
            "plan.steps<span class=\"footnote-wrapper\">(0)</span>.status"
            == PlanStepStatus.FAILED
        )

    asyncio.run(scenario())


def test_plan_step_limit() -> None:
    registry = create_registry()

    plan = ExecutionPlan(
        goal="Слишком большой план",
        steps=[
            PlanStep(
                step_id=f"step-{index}",
                tool_name="echo",
                arguments={
                    "text": str(index),
                },
            )
            for index in range(5)
        ],
    )

    validation = PlanValidator.validate(
        plan,
        registry,
        max_steps=3,
    )

    assert not validation.valid
    assert any(
        "при лимите 3" in error
        for error in validation.errors
    )


def test_self_dependency_is_rejected() -> None:
    registry = create_registry()

    plan = ExecutionPlan(
        goal="Проверить зависимость",
        steps=[
            PlanStep(
                step_id="self",
                tool_name="echo",
                arguments={
                    "text": "self",
                },
                depends_on=["self"],
            ),
        ],
    )

    validation = PlanValidator.validate(
        plan,
        registry,
    )

    assert not validation.valid
    assert any(
        "не может зависеть от себя" in error
        for error in validation.errors
    )


def test_unknown_dependency_is_rejected() -> None:
    registry = create_registry()

    plan = ExecutionPlan(
        goal="Проверить неизвестную зависимость",
        steps=[
            PlanStep(
                step_id="step-one",
                tool_name="echo",
                arguments={
                    "text": "one",
                },
                depends_on=["missing-step"],
            ),
        ],
    )

    validation = PlanValidator.validate(
        plan,
        registry,
    )

    assert not validation.valid
    assert any(
        "неизвестного шага" in error
        for error in validation.errors
    )


def test_duplicate_step_ids_are_rejected() -> None:
    registry = create_registry()

    plan = ExecutionPlan(
        goal="Проверить дубликаты",
        steps=[
            PlanStep(
                step_id="duplicate",
                tool_name="echo",
                arguments={
                    "text": "one",
                },
            ),
            PlanStep(
                step_id="duplicate",
                tool_name="echo",
                arguments={
                    "text": "two",
                },
            ),
        ],
    )

    validation = PlanValidator.validate(
        plan,
        registry,
    )

    assert not validation.valid
    assert any(
        "должны быть уникальными" in error
        for error in validation.errors
    )


def test_noncritical_failure_allows_independent_step() -> None:
    async def scenario() -> None:
        registry = create_registry()

        executor = PlanExecutor(
            registry=registry,
            runner=ToolRunner(registry),
        )

        plan = ExecutionPlan(
            goal="Продолжить после некритической ошибки",
            steps=[
                PlanStep(
                    step_id="optional-failure",
                    tool_name="fail",
                    arguments={},
                    critical=False,
                ),
                PlanStep(
                    step_id="independent",
                    tool_name="echo",
                    arguments={
                        "text": "completed",
                    },
                    critical=True,
                ),
            ],
        )

        result = await executor.execute(
            plan,
            session_id="session-test",
            turn_id="turn-test",
        )

        assert not result.success
        assert result.failed_steps == 1
        assert result.completed_steps == 1

        assert (
            plan.steps[0].status
            == PlanStepStatus.FAILED
        )
        assert (
            plan.steps[1].status
            == PlanStepStatus.COMPLETED
        )

    asyncio.run(scenario())


def test_failed_dependency_skips_dependent_step() -> None:
    async def scenario() -> None:
        registry = create_registry()

        executor = PlanExecutor(
            registry=registry,
            runner=ToolRunner(registry),
        )

        plan = ExecutionPlan(
            goal="Пропустить зависимый шаг",
            steps=[
                PlanStep(
                    step_id="failed",
                    tool_name="fail",
                    arguments={},
                    critical=False,
                ),
                PlanStep(
                    step_id="dependent",
                    tool_name="echo",
                    arguments={
                        "text": "never",
                    },
                    depends_on=["failed"],
                ),
            ],
        )

        result = await executor.execute(
            plan,
            session_id="session-test",
            turn_id="turn-test",
        )

        assert not result.success
        assert result.failed_steps == 1
        assert result.skipped_steps == 1

        assert (
            plan.steps[1].status
            == PlanStepStatus.SKIPPED
        )

    asyncio.run(scenario())


def test_plan_cancellation() -> None:
    async def scenario() -> None:
        registry = create_registry()

        executor = PlanExecutor(
            registry=registry,
            runner=ToolRunner(registry),
        )

        cancellation_event = asyncio.Event()
        cancellation_event.set()

        plan = ExecutionPlan(
            goal="Отменённый план",
            steps=[
                PlanStep(
                    step_id="one",
                    tool_name="echo",
                    arguments={
                        "text": "one",
                    },
                ),
                PlanStep(
                    step_id="two",
                    tool_name="echo",
                    arguments={
                        "text": "two",
                    },
                ),
            ],
        )

        result = await executor.execute(
            plan,
            session_id="session-test",
            turn_id="turn-test",
            cancellation_event=(
                cancellation_event
            ),
        )

        assert not result.success
        assert result.skipped_steps == 2

        assert all(
            step.status
            == PlanStepStatus.CANCELLED
            for step in plan.steps
        )

    asyncio.run(scenario())


def test_plan_time_budget() -> None:
    async def scenario() -> None:
        registry = create_registry()

        executor = PlanExecutor(
            registry=registry,
            runner=ToolRunner(registry),
            budget=PlanBudget(
                max_steps=10,
                max_wall_time_seconds=0.0,
            ),
        )

        plan = ExecutionPlan(
            goal="План с нулевым временем",
            steps=[
                PlanStep(
                    step_id="one",
                    tool_name="echo",
                    arguments={
                        "text": "one",
                    },
                ),
            ],
        )

        result = await executor.execute(
            plan,
            session_id="session-test",
            turn_id="turn-test",
        )

        assert not result.success
        assert (
            result.error_code
            == "PLAN_TIME_BUDGET_EXHAUSTED"
        )

    asyncio.run(scenario())


def test_plan_result_converts_to_tool_result() -> None:
    async def scenario() -> None:
        registry = create_registry()

        executor = PlanExecutor(
            registry=registry,
            runner=ToolRunner(registry),
        )

        plan = ExecutionPlan(
            goal="Проверить преобразование",
            steps=[
                PlanStep(
                    step_id="one",
                    tool_name="echo",
                    arguments={
                        "text": "one",
                    },
                ),
            ],
        )

        execution_result = await executor.execute(
            plan,
            session_id="session-test",
            turn_id="turn-test",
        )

        tool_result = (
            execution_result.to_tool_result()
        )

        assert tool_result.success
        assert (
            tool_result.data["completed_steps"]
            == 1
        )
        assert (
            tool_result.verification.verified
            is True
        )

    asyncio.run(scenario())
