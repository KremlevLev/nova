# modules/tools/tasks.py
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable


logger = logging.getLogger("TaskScheduler")


class TaskScheduler:
    def __init__(
        self,
        storage_path: str = "data/tasks/tasks.json",
    ) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.tasks: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._load_tasks()

    def _load_tasks(self) -> None:
        if not self.storage_path.exists():
            return

        try:
            with self.storage_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                loaded = json.load(file)

            if not isinstance(loaded, list):
                raise ValueError(
                    "Корень файла задач должен быть массивом."
                )

            self.tasks = [
                task
                for task in loaded
                if isinstance(task, dict)
            ]
        except Exception:
            logger.exception("Не удалось загрузить задачи.")
            self.tasks = []

    def _save_tasks(self) -> None:
        with self._lock:
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix="tasks_",
                suffix=".json.tmp",
                dir=str(self.storage_path.parent),
            )

            try:
                with os.fdopen(
                    file_descriptor,
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(
                        self.tasks,
                        file,
                        ensure_ascii=False,
                        indent=2,
                    )
                    file.flush()
                    os.fsync(file.fileno())

                os.replace(
                    temporary_name,
                    self.storage_path,
                )
            except Exception:
                try:
                    os.unlink(temporary_name)
                except OSError:
                    pass
                raise

    @staticmethod
    def _parse_time(
        time_str: str,
        now: dt.datetime,
    ) -> dt.datetime:
        clean = time_str.strip()

        if clean.startswith("+"):
            minutes = int(clean[1:])
            if minutes <= 0 or minutes > 10080:
                raise ValueError(
                    "Интервал должен быть от 1 до 10080 минут."
                )
            return now + dt.timedelta(minutes=minutes)

        if len(clean) == 5 and clean[2] == ":":
            hour, minute = map(int, clean.split(":"))
            target = now.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

            if target <= now:
                target += dt.timedelta(days=1)

            return target

        formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        )

        for time_format in formats:
            try:
                return dt.datetime.strptime(clean, time_format)
            except ValueError:
                continue

        raise ValueError("Неподдерживаемый формат времени.")

    def add_reminder(
        self,
        time_str: str,
        message: str,
    ) -> str:
        clean_message = message.strip()

        if not clean_message:
            return "Ошибка: Текст напоминания пуст."

        if len(clean_message) > 1000:
            return "Ошибка: Текст напоминания слишком длинный."

        now = dt.datetime.now()

        try:
            target_time = self._parse_time(time_str, now)
        except (ValueError, TypeError) as exc:
            return (
                f"Ошибка: Неверный формат времени '{time_str}': "
                f"{exc}"
            )

        new_task = {
            "id": f"task_{uuid.uuid4().hex}",
            "type": "reminder",
            "time": target_time.isoformat(timespec="seconds"),
            "message": clean_message,
            "status": "pending",
            "created_at": now.isoformat(timespec="seconds"),
            "delivered_at": None,
        }

        with self._lock:
            self.tasks.append(new_task)
            self._save_tasks()

        if target_time.date() == now.date():
            formatted_time = target_time.strftime(
                "%H:%M сегодня"
            )
        else:
            formatted_time = target_time.strftime(
                "%d.%m.%Y в %H:%M"
            )

        return (
            f"Напоминание установлено на {formatted_time}. "
            f"Идентификатор: {new_task['id']}."
        )

    def list_reminders(self) -> str:
        with self._lock:
            active_tasks = [
                task.copy()
                for task in self.tasks
                if task.get("status", "pending")
                in {"pending", "due", "queued"}
            ]

        if not active_tasks:
            return "У вас нет активных напоминаний."

        active_tasks.sort(key=lambda item: item.get("time", ""))

        lines = ["Ваши активные напоминания:"]

        for index, task in enumerate(active_tasks, 1):
            lines.append(
                f"{index}. [{task.get('time')}] "
                f"{task.get('message')} "
                f"(ID: {task.get('id')})"
            )

        return "\n".join(lines)

    def get_pending_tasks(self) -> list[dict[str, Any]]:
        now = dt.datetime.now()
        pending: list[dict[str, Any]] = []

        with self._lock:
            for task in self.tasks:
                if task.get("status", "pending") != "pending":
                    continue

                try:
                    task_time = dt.datetime.fromisoformat(
                        str(task["time"])
                    )
                except (KeyError, TypeError, ValueError):
                    task["status"] = "invalid"
                    logger.warning(
                        "Задача %s содержит поврежденное время.",
                        task.get("id"),
                    )
                    continue

                if now >= task_time:
                    task["status"] = "due"
                    pending.append(task.copy())

            if pending:
                self._save_tasks()

        return pending

    def mark_delivered(self, task_id: str) -> bool:
        with self._lock:
            for task in self.tasks:
                if task.get("id") == task_id:
                    task["status"] = "delivered"
                    task["delivered_at"] = dt.datetime.now().isoformat(
                        timespec="seconds"
                    )
                    self._save_tasks()
                    return True

        return False

    def mark_failed(
        self,
        task_id: str,
        reason: str,
    ) -> bool:
        with self._lock:
            for task in self.tasks:
                if task.get("id") == task_id:
                    task["status"] = "failed"
                    task["failure_reason"] = reason
                    self._save_tasks()
                    return True

        return False

    def cancel_reminder(self, task_id: str) -> str:
        with self._lock:
            for task in self.tasks:
                if task.get("id") == task_id:
                    if task.get("status") == "delivered":
                        return "Напоминание уже доставлено."

                    task["status"] = "cancelled"
                    self._save_tasks()
                    return "Напоминание отменено."

        return "Ошибка: Напоминание с таким ID не найдено."


async def reminder_checker_worker(
    scheduler: TaskScheduler,
    notify: Callable[[str], Awaitable[None]],
    shutdown_event: asyncio.Event,
) -> None:
    while not shutdown_event.is_set():
        try:
            pending = await asyncio.to_thread(
                scheduler.get_pending_tasks
            )

            for task in pending:
                try:
                    await notify(
                        f"Внимание. Напоминаю: {task['message']}"
                    )
                    await asyncio.to_thread(
                        scheduler.mark_delivered,
                        task["id"],
                    )
                except Exception as exc:
                    logger.exception(
                        "Не удалось доставить напоминание %s.",
                        task.get("id"),
                    )
                    await asyncio.to_thread(
                        scheduler.mark_failed,
                        task["id"],
                        str(exc),
                    )

        except Exception:
            logger.exception("Ошибка фонового планировщика.")

        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=1.0,
            )
        except asyncio.TimeoutError:
            pass
