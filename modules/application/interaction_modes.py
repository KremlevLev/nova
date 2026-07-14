# modules/application/interaction_modes.py
from __future__ import annotations

import asyncio
import logging
from typing import Any

from modules.application.preferences import (
    PreferencesManager,
    PreferencesSnapshot,
)
from modules.domain.state import RuntimeState
from modules.input_hub.models import InputMode


logger = logging.getLogger("InteractionModes")


class InteractionModeManager:
    """
    Единая точка переключения режимов взаимодействия Nova.

    Не изменяйте InputMode напрямую через PreferencesManager,
    если доступен InteractionModeManager.
    """

    def __init__(
        self,
        *,
        preferences: PreferencesManager,
        runtime: RuntimeState,
        speech=None,
        wake_runtime=None,
    ) -> None:
        self.preferences = preferences
        self.runtime = runtime
        self.speech = speech
        self.wake_runtime = wake_runtime

        self._lock = asyncio.Lock()

    def attach_wake_runtime(
        self,
        wake_runtime,
    ) -> None:
        self.wake_runtime = wake_runtime

    async def set_mode(
        self,
        mode: InputMode,
    ) -> PreferencesSnapshot:
        async with self._lock:
            previous_mode = (
                self.preferences
                .snapshot()
                .input_mode
            )

            if previous_mode == mode:
                return self.preferences.snapshot()

            logger.info(
                "Переключение режима: %s -> %s",
                previous_mode.value,
                mode.value,
            )

            if self.speech is not None:
                await self.speech.interrupt()

            snapshot = (
                self.preferences.set_input_mode(
                    mode
                )
            )

            if mode == InputMode.CONTINUOUS:
                await self.runtime.activate()

            elif mode in {
                InputMode.WAKE_WORD,
                InputMode.PUSH_TO_TALK,
                InputMode.TEXT_ONLY,
                InputMode.PRIVACY,
                InputMode.SLEEP,
            }:
                await self.runtime.sleep()

            return snapshot

    async def set_mode_from_string(
        self,
        mode_name: str,
    ) -> PreferencesSnapshot:
        try:
            mode = InputMode(
                mode_name.strip().lower()
            )
        except ValueError as exc:
            valid_modes = ", ".join(
                mode.value
                for mode in InputMode
            )

            raise ValueError(
                (
                    f"Неизвестный режим '{mode_name}'. "
                    f"Допустимые режимы: {valid_modes}."
                )
            ) from exc

        return await self.set_mode(mode)

    def snapshot(self) -> dict[str, Any]:
        return (
            self.preferences
            .snapshot()
            .to_dict()
        )
