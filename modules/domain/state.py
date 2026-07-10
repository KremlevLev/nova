# modules/domain/state.py
from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from typing import Callable


logger = logging.getLogger("RuntimeState")


class AssistantState(StrEnum):
    SLEEPING = "СПИТ"
    LISTENING = "СЛУШАЕТ"
    TRANSCRIBING = "РАСПОЗНАЕТ"
    THINKING = "ДУМАЕТ"
    WAITING_PERMISSION = "ЖДЕТ РАЗРЕШЕНИЕ"
    EXECUTING_TOOL = "ВЫПОЛНЯЕТ"
    SPEAKING = "ГОВОРИТ"
    ERROR = "ОШИБКА"
    SHUTTING_DOWN = "ЗАВЕРШАЕТ РАБОТУ"


class RuntimeState:
    def __init__(
        self,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._state = AssistantState.SLEEPING
        self._active = False
        self._shutdown_event = asyncio.Event()
        self._activation_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._status_callback = status_callback

    @property
    def state(self) -> AssistantState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._active
    @property
    def shutdown_event(self) -> asyncio.Event:
        return self._shutdown_event

    @property
    def is_shutting_down(self) -> bool:
        return self._shutdown_event.is_set()

    async def set_state(self, state: AssistantState) -> None:
        async with self._lock:
            self._state = state

        if self._status_callback:
            try:
                self._status_callback(state.value)
            except Exception:
                logger.exception("Не удалось обновить состояние интерфейса.")

    async def activate(self) -> None:
        self._active = True
        self._activation_event.set()
        await self.set_state(AssistantState.LISTENING)

    async def sleep(self) -> None:
        self._active = False
        await self.set_state(AssistantState.SLEEPING)

    async def toggle(self) -> bool:
        if self._active:
            await self.sleep()
        else:
            await self.activate()
        return self._active

    async def wait_until_active(self) -> None:
        while not self._active and not self.is_shutting_down:
            self._activation_event.clear()
            await self._activation_event.wait()

    async def request_shutdown(self) -> None:
        self._active = False
        self._shutdown_event.set()
        self._activation_event.set()
        await self.set_state(AssistantState.SHUTTING_DOWN)

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()
