# modules/ui/core_bridge.py
from __future__ import annotations

import asyncio
import logging
from typing import Any

from modules.tools.permissions import (
    PermissionManager,
)
from modules.ui.desktop_protocol import (
    validate_command,
)
from modules.ui.desktop_service import (
    DesktopService,
)


logger = logging.getLogger("CoreDesktopBridge")


class CoreDesktopBridge:
    """
    Передаёт состояние Nova в UI и маршрутизирует команды UI.
    """

    def __init__(
        self,
        *,
        desktop: DesktopService,
        process_manager,
        memory_store,
        permission_manager: PermissionManager,
        llm,
        runtime,
    ) -> None:
        self.desktop = desktop
        self.process_manager = process_manager
        self.memory_store = memory_store
        self.permission_manager = (
            permission_manager
        )
        self.llm = llm
        self.runtime = runtime

    async def run(
        self,
        shutdown_event: asyncio.Event,
    ) -> None:
        while not shutdown_event.is_set():
            try:
                await self.publish_snapshots()

                for command in (
                    self.desktop.get_commands()
                ):
                    await self.handle_command(
                        command
                    )

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Ошибка DesktopBridge."
                )

            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=0.5,
                )
            except asyncio.TimeoutError:
                pass

    async def publish_snapshots(self) -> None:
        process_result = await asyncio.to_thread(
            self.process_manager.list_processes
        )

        process_data = (
            process_result.data.get(
                "processes",
                [],
            )
            if process_result.success
            else []
        )

        memory_data = await asyncio.to_thread(
            self.memory_store.search,
            "",
            limit=200,
        )

        permission_data = (
            self.permission_manager.pending_requests()
        )

        model_data = self.llm.provider_health()

        self.desktop.publish(
            "runtime",
            {
                "state": self.runtime.state.value,
                "active": self.runtime.is_active,
                "shutting_down": (
                    self.runtime.is_shutting_down
                ),
            },
        )

        self.desktop.publish(
            "processes",
            {
                "items": process_data,
            },
        )

        self.desktop.publish(
            "memories",
            {
                "items": memory_data,
            },
        )

        self.desktop.publish(
            "permissions",
            {
                "items": permission_data,
            },
        )

        self.desktop.publish(
            "models",
            model_data,
        )

    async def handle_command(
        self,
        command: dict[str, Any],
    ) -> None:
        valid, error = validate_command(
            command
        )

        command_id = str(
            command.get(
                "command_id",
                "unknown",
            )
        )

        if not valid:
            self._publish_command_result(
                command_id,
                success=False,
                message=error or "Некорректная команда.",
            )
            return

        action = command["action"]
        payload = command.get(
            "payload",
            {},
        )

        try:
            if action == "refresh":
                await self.publish_snapshots()

                self._publish_command_result(
                    command_id,
                    success=True,
                    message="Данные обновлены.",
                )
                return

            if action == "stop_process":
                process_id = str(
                    payload.get("process_id", "")
                )

                result = await asyncio.to_thread(
                    self.process_manager.stop_process,
                    process_id,
                    force=bool(
                        payload.get(
                            "force",
                            False,
                        )
                    ),
                )

                self._publish_tool_result(
                    command_id,
                    result,
                )
                return

            if action == "delete_memory":
                key = str(
                    payload.get("key", "")
                )

                success = await asyncio.to_thread(
                    self.memory_store.delete,
                    key,
                )

                self._publish_command_result(
                    command_id,
                    success=bool(success),
                    message=(
                        f"Факт '{key}' удалён."
                        if success
                        else
                        f"Не удалось удалить '{key}'."
                    ),
                )
                return

            if action == "clear_memories":
                success = await asyncio.to_thread(
                    self.memory_store.clear_all
                )

                self._publish_command_result(
                    command_id,
                    success=bool(success),
                    message=(
                        "Память очищена."
                        if success
                        else
                        "Не удалось очистить память."
                    ),
                )
                return

            if action == "confirm_permission":
                operation_id = str(
                    payload.get(
                        "operation_id",
                        "",
                    )
                )

                success = (
                    self.permission_manager.confirm(
                        operation_id
                    )
                )

                self._publish_command_result(
                    command_id,
                    success=success,
                    message=(
                        "Операция разрешена."
                        if success
                        else
                        "Запрос разрешения не найден."
                    ),
                )
                return

            if action == "deny_permission":
                operation_id = str(
                    payload.get(
                        "operation_id",
                        "",
                    )
                )

                success = (
                    self.permission_manager.deny(
                        operation_id
                    )
                )

                self._publish_command_result(
                    command_id,
                    success=success,
                    message=(
                        "Операция запрещена."
                        if success
                        else
                        "Запрос разрешения не найден."
                    ),
                )
                return

            self._publish_command_result(
                command_id,
                success=False,
                message=(
                    f"Неизвестная команда UI: "
                    f"{action}"
                ),
            )

        except Exception as exc:
            logger.exception(
                "Ошибка команды UI %s.",
                action,
            )

            self._publish_command_result(
                command_id,
                success=False,
                message=str(exc),
            )

    def _publish_tool_result(
        self,
        command_id: str,
        result,
    ) -> None:
        self.desktop.publish(
            "command_result",
            {
                "command_id": command_id,
                **result.to_dict(),
            },
        )

    def _publish_command_result(
        self,
        command_id: str,
        *,
        success: bool,
        message: str,
    ) -> None:
        self.desktop.publish(
            "command_result",
            {
                "command_id": command_id,
                "success": success,
                "message": message,
            },
        )
