# tests/test_plan_service.py
from __future__ import annotations

import asyncio

from modules.agent.plan_service import (
    PlanService,
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


def create_service() -> PlanService:
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
                data={
                    "text": text,
                },
                verification=VerificationResult(
                    verified=True,
                    method="echo",
                    confidence=1.0,
                ),
            ),
            category=ToolCategory.SYSTEM_READ,
            risk=RiskLevel.READ_ONLY,
        )
    )

    runner = ToolRunner(registry)

    return PlanService(
        registry=registry,
        runner=runner,
    )


def test_execute_plan() -> None:
    async def scenario() -> None:
        service = create_service()

        result = await service.execute_plan(
            goal="Выполнить два действия",
            steps=[
                {
                    "step_id": "first",
                    "tool_name": "echo",
                    "arguments": {
                        "text": "one",
                    },
                },
                {
                    "step_id": "second",
                    "tool_name": "echo",
                    "arguments": {
                        "text": "two",
                    },
                    "depends_on": ["first"],
                },
            ],
        )

        assert result.success
        assert (
            result.data["completed_steps"]
            == 2
        )

    asyncio.run(scenario())


def test_execute_plan_rejects_empty_goal() -> None:
    async def scenario() -> None:
        service = create_service()

        result = await service.execute_plan(
            goal="",
            steps=[],
        )

        assert not result.success
        assert result.code == "EMPTY_PLAN_GOAL"

    asyncio.run(scenario())


def test_execute_plan_rejects_unknown_tool() -> None:
    async def scenario() -> None:
        service = create_service()

        result = await service.execute_plan(
            goal="Некорректный план",
            steps=[
                {
                    "step_id": "one",
                    "tool_name": "unknown",
                    "arguments": {},
                }
            ],
        )

        assert not result.success
        assert result.code == "INVALID_PLAN"

    asyncio.run(scenario())


def test_get_unknown_plan_status() -> None:
    service = create_service()

    result = service.get_plan_status(
        "missing-plan"
    )

    assert not result.success
    assert result.code == "PLAN_NOT_FOUND"


def test_cancel_unknown_plan() -> None:
    service = create_service()

    result = service.cancel_plan(
        "missing-plan"
    )

    assert not result.success
    assert (
        result.code
        == "ACTIVE_PLAN_NOT_FOUND"
    )
