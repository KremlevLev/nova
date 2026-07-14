# modules/agent/background_plans.py
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from modules.agent.plan_service import PlanService
from modules.domain.results import ToolResult


logger = logging.getLogger("BackgroundPlans")


class BackgroundPlanStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class BackgroundPlan:
    background_id: str
    goal: str
    steps: list[dict[str, Any]]

    session_id: str
    turn_id: str

    status: BackgroundPlanStatus = (
        BackgroundPlanStatus.QUEUED
    )

    created_at: float = field(
        default_factory=time.time
    )
    started_at: float | None = None
    finished_at: float | None = None

    result: ToolResult | None = None
    error: str | None = None

    task: asyncio.Task[None] | None = field(
        default=None,
        repr=False,
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "background_id": self.background_id,
            "goal": self.goal,
            "steps_count": len(self.steps),
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "result": (
                self.result.to_dict()
                if self.result is not None
                else None
            ),
            "error": self.error,
        }


class BackgroundPlanManager:
    """
    Запускает PlanService в фоновых asyncio-задачах.

    Пользователь может:
    - получить status;
    - перечислить задачи;
    - отменить задачу;
    - продолжать общаться с Nova, пока план выполняется.
    """

    def __init__(
        self,
        plan_service: PlanService,
    ) -> None:
        self.plan_service = plan_service

        self._plans: dict[
            str,
            BackgroundPlan,
        ] = {}

        self._lock = asyncio.Lock()
        self._closed = False

    async def start_plan(
        self,
        goal: str,
        steps: list[dict[str, Any]],
        *,
        session_id: str = "background-session",
        turn_id: str | None = None,
    ) -> ToolResult:
        if self._closed:
            return ToolResult.failure(
                "BACKGROUND_MANAGER_CLOSED",
                "Менеджер фоновых планов закрыт.",
            )

        if not goal.strip():
            return ToolResult.failure(
                "EMPTY_PLAN_GOAL",
                "Цель фонового плана не указана.",
            )

        if not isinstance(steps, list) or not steps:
            return ToolResult.failure(
                "INVALID_PLAN_STEPS",
                (
                    "Фоновый план должен содержать "
                    "хотя бы один шаг."
                ),
            )

        background_id = (
            f"background_{uuid.uuid4().hex}"
        )

        resolved_turn_id = (
            turn_id
            or f"background_turn_{uuid.uuid4().hex}"
        )

        record = BackgroundPlan(
            background_id=background_id,
            goal=goal.strip(),
            steps=steps,
            session_id=session_id,
            turn_id=resolved_turn_id,
        )

        async with self._lock:
            self._plans[background_id] = record

            record.task = asyncio.create_task(
                self._run_plan(record),
                name=(
                    f"nova-background-plan-"
                    f"{background_id}"
                ),
            )

        return ToolResult.ok(
            (
                "Фоновый план поставлен в очередь. "
                f"Идентификатор: {background_id}."
            ),
            data={
                "background_id": background_id,
                "status": record.status.value,
                "goal": record.goal,
                "steps_count": len(steps),
            },
        )

    async def _run_plan(
        self,
        record: BackgroundPlan,
    ) -> None:
        record.status = BackgroundPlanStatus.RUNNING
        record.started_at = time.time()

        logger.info(
            "Фоновый план запущен: %s goal=%s",
            record.background_id,
            record.goal,
        )

        try:
            result = await self.plan_service.execute_plan(
                goal=record.goal,
                steps=record.steps,
                session_id=record.session_id,
                turn_id=record.turn_id,
            )

            record.result = result

            if record.status == (
                BackgroundPlanStatus.CANCELLING
            ):
                record.status = (
                    BackgroundPlanStatus.CANCELLED
                )
            elif result.success:
                record.status = (
                    BackgroundPlanStatus.COMPLETED
                )
            else:
                record.status = (
                    BackgroundPlanStatus.FAILED
                )

        except asyncio.CancelledError:
            record.status = (
                BackgroundPlanStatus.CANCELLED
            )

            record.result = ToolResult.failure(
                "BACKGROUND_PLAN_CANCELLED",
                "Фоновый план отменён.",
            )

            raise

        except Exception as exc:
            logger.exception(
                "Фоновый план %s упал.",
                record.background_id,
            )

            record.status = (
                BackgroundPlanStatus.FAILED
            )
            record.error = str(exc)

            record.result = ToolResult.failure(
                "BACKGROUND_PLAN_FAILED",
                (
                    "Фоновый план завершился "
                    f"необработанной ошибкой: {exc}"
                ),
            )

        finally:
            record.finished_at = time.time()

            logger.info(
                "Фоновый план завершён: %s status=%s",
                record.background_id,
                record.status.value,
            )

    async def get_status(
        self,
        background_id: str,
    ) -> ToolResult:
        async with self._lock:
            record = self._plans.get(
                background_id
            )

        if record is None:
            return ToolResult.failure(
                "BACKGROUND_PLAN_NOT_FOUND",
                (
                    f"Фоновый план '{background_id}' "
                    "не найден."
                ),
            )

        return ToolResult.ok(
            (
                f"Статус фонового плана: "
                f"{record.status.value}."
            ),
            data=record.to_dict(),
        )

    async def list_plans(self) -> ToolResult:
        async with self._lock:
            records = list(
                self._plans.values()
            )

        records.sort(
            key=lambda item: item.created_at,
            reverse=True,
        )

        return ToolResult.ok(
            (
                f"Найдено фоновых планов: "
                f"{len(records)}."
            ),
            data={
                "count": len(records),
                "plans": [
                    record.to_dict()
                    for record in records
                ],
            },
        )

    async def cancel_plan(
        self,
        background_id: str,
    ) -> ToolResult:
        async with self._lock:
            record = self._plans.get(
                background_id
            )

        if record is None:
            return ToolResult.failure(
                "BACKGROUND_PLAN_NOT_FOUND",
                (
                    f"Фоновый план '{background_id}' "
                    "не найден."
                ),
            )

        if record.status in {
            BackgroundPlanStatus.COMPLETED,
            BackgroundPlanStatus.FAILED,
            BackgroundPlanStatus.CANCELLED,
        }:
            return ToolResult.ok(
                (
                    "Фоновый план уже завершён. "
                    f"Статус: {record.status.value}."
                ),
                data=record.to_dict(),
            )

        record.status = (
            BackgroundPlanStatus.CANCELLING
        )

        if (
            record.task is not None
            and not record.task.done()
        ):
            record.task.cancel()

            await asyncio.gather(
                record.task,
                return_exceptions=True,
            )

        return ToolResult.ok(
            f"Фоновый план '{background_id}' отменён.",
            data=record.to_dict(),
        )

    async def close(self) -> None:
        self._closed = True

        async with self._lock:
            tasks = [
                record.task
                for record in self._plans.values()
                if (
                    record.task is not None
                    and not record.task.done()
                )
            ]

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        logger.info(
            "Менеджер фоновых планов закрыт."
        )
