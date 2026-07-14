# tests/test_background_plans.py
from __future__ import annotations

import asyncio

from modules.agent.background_plans import (
    BackgroundPlanManager,
    BackgroundPlanStatus,
)
from modules.domain.results import ToolResult


class FakePlanService:
    async def execute_plan(
        self,
        goal,
        steps,
        session_id,
        turn_id,
    ):
        await asyncio.sleep(0.01)

        return ToolResult.ok(
            "План выполнен.",
            data={
                "goal": goal,
            },
        )


class SlowPlanService:
    async def execute_plan(
        self,
        goal,
        steps,
        session_id,
        turn_id,
    ):
        await asyncio.sleep(10)

        return ToolResult.ok("Готово.")


def test_background_plan_completes() -> None:
    async def scenario() -> None:
        manager = BackgroundPlanManager(
            FakePlanService()
        )

        start_result = await manager.start_plan(
            goal="Тест",
            steps=[
                {
                    "step_id": "one",
                    "tool_name": "echo",
                    "arguments": {},
                }
            ],
        )

        assert start_result.success

        background_id = (
            start_result.data["background_id"]
        )

        await asyncio.sleep(0.05)

        status_result = await manager.get_status(
            background_id
        )

        assert status_result.success
        assert (
            status_result.data["status"]
            == BackgroundPlanStatus.COMPLETED.value
        )

        await manager.close()

    asyncio.run(scenario())


def test_background_plan_can_be_cancelled() -> None:
    async def scenario() -> None:
        manager = BackgroundPlanManager(
            SlowPlanService()
        )

        start_result = await manager.start_plan(
            goal="Долгий тест",
            steps=[
                {
                    "step_id": "one",
                    "tool_name": "echo",
                    "arguments": {},
                }
            ],
        )

        background_id = (
            start_result.data["background_id"]
        )

        cancel_result = await manager.cancel_plan(
            background_id
        )

        assert cancel_result.success

        status_result = await manager.get_status(
            background_id
        )

        assert (
            status_result.data["status"]
            == BackgroundPlanStatus.CANCELLED.value
        )

        await manager.close()

    asyncio.run(scenario())


def test_unknown_background_plan() -> None:
    async def scenario() -> None:
        manager = BackgroundPlanManager(
            FakePlanService()
        )

        result = await manager.get_status(
            "missing"
        )

        assert not result.success
        assert (
            result.code
            == "BACKGROUND_PLAN_NOT_FOUND"
        )

        await manager.close()

    asyncio.run(scenario())


def test_list_background_plans() -> None:
    async def scenario() -> None:
        manager = BackgroundPlanManager(
            FakePlanService()
        )

        await manager.start_plan(
            goal="Первый",
            steps=[
                {
                    "step_id": "one",
                    "tool_name": "echo",
                    "arguments": {},
                }
            ],
        )

        result = await manager.list_plans()

        assert result.success
        assert result.data["count"] == 1

        await manager.close()

    asyncio.run(scenario())
