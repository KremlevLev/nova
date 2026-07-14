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

    async def set_mode(
        self,
        mode: InputMode,
    ) -> PreferencesSnapshot:
        """
        Устанавливает режим и синхронизирует RuntimeState.

        Метод намеренно применяет состояние runtime даже тогда,
        когда выбранный InputMode уже записан в PreferencesManager.
        Это исправляет рассинхронизацию вида:

            preferences = WAKE_WORD
            runtime = active
        """
        async with self._lock:
            previous_mode = (
                self.preferences
                .snapshot()
                .input_mode
            )

            mode_changed = (
                previous_mode != mode
            )

            if mode_changed:
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
            else:
                logger.debug(
                    (
                        "Режим %s уже выбран. "
                        "Синхронизирую RuntimeState."
                    ),
                    mode.value,
                )

                snapshot = (
                    self.preferences.snapshot()
                )

            # CONTINUOUS — единственный режим, в котором обычный
            # VoiceListener должен непрерывно слушать микрофон.
            if mode == InputMode.CONTINUOUS:
                if not self.runtime.is_active:
                    await self.runtime.activate()

            else:
                # WAKE_WORD слушает через отдельный лёгкий detector.
                # PUSH_TO_TALK ждёт удержания горячей клавиши.
                # TEXT_ONLY, PRIVACY и SLEEP не используют
                # непрерывный VoiceListener.
                if self.runtime.is_active:
                    await self.runtime.sleep()
                else:
                    # Даже при уже неактивном runtime обновляем
                    # визуальное состояние на СПИТ.
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
