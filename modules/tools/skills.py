# modules/tools/skills.py
from __future__ import annotations

import logging
import time
from typing import Callable

from modules.domain.results import ToolResult
from modules.tools.app_indexer import WindowsAppIndexer


logger = logging.getLogger("Skills")


class WindowsSkills:
    def __init__(
        self,
        *,
        app_launcher: WindowsAppIndexer,
        list_windows: Callable[..., str],
        focus_window: Callable[..., str],
        press_hotkey: Callable[..., str],
        type_text: Callable[..., str],
        get_active_window_title: Callable[..., str],
    ) -> None:
        self.app_launcher = app_launcher
        self.list_windows = list_windows
        self.focus_window = focus_window
        self.press_hotkey = press_hotkey
        self.type_text = type_text
        self.get_active_window_title = (
        get_active_window_title
    )

        

    @staticmethod
    def _result_failed(result: str) -> bool:
        lowered = result.lower()

        markers = (
            "ошибка",
            "не удалось",
            "не найден",
            "отказ",
            "заблокирован",
            "access denied",
            "permission denied",
        )

        return any(marker in lowered for marker in markers)

    def write_in_application(
        self,
        app_name: str,
        text: str,
        create_new_document: bool = True,
    ) -> ToolResult:
        clean_app_name = app_name.strip()
        clean_text = text.strip()

        if not clean_app_name:
            return ToolResult.failure(
                "EMPTY_APPLICATION_NAME",
                "Название приложения не указано.",
            )

        if not clean_text:
            return ToolResult.failure(
                "EMPTY_TEXT",
                "Текст для записи не указан.",
            )

        if len(clean_text) > 100_000:
            return ToolResult.failure(
                "TEXT_TOO_LARGE",
                "За один вызов разрешено ввести до 100000 символов.",
            )

        launch_success, launch_message = (
            self.app_launcher.launch_by_name(
                clean_app_name
            )
        )

        if not launch_success:
            return ToolResult.failure(
                "APPLICATION_LAUNCH_FAILED",
                launch_message,
            )

        # Даем Electron/Win32-приложению закончить активацию окна.
        time.sleep(0.8)

        focus_result = str(
            self.focus_window(clean_app_name)
        )

        if self._result_failed(focus_result):
            # Для русских алиасов заголовок окна может быть английским.
            match = self.app_launcher.find_app(
                clean_app_name
            )

            if match is not None:
                focus_result = str(
                    self.focus_window(
                        match.matched_name
                    )
                )

        if self._result_failed(focus_result):
            return ToolResult.failure(
                "WINDOW_FOCUS_FAILED",
                (
                    f"Приложение запущено, но его окно не удалось "
                    f"сфокусировать: {focus_result}"
                ),
                data={
                    "launch_message": launch_message,
                },
            )

        if create_new_document:
            hotkey_result = str(
                self.press_hotkey("ctrl+n")
            )

            if self._result_failed(hotkey_result):
                return ToolResult.failure(
                    "NEW_DOCUMENT_FAILED",
                    (
                        "Окно сфокусировано, но не удалось создать "
                        f"новый документ: {hotkey_result}"
                    ),
                )

            time.sleep(0.3)

        active_title = str(
            self.get_active_window_title()
        ).strip()

        match = self.app_launcher.find_app(
            clean_app_name
        )

        expected_names = {
            clean_app_name.lower(),
        }

        if match is not None:
            expected_names.add(
                match.matched_name.lower()
            )

        if not active_title or not any(
            expected_name in active_title.lower()
            for expected_name in expected_names
        ):
            return ToolResult.failure(
                "ACTIVE_WINDOW_CHANGED",
                (
                    "Ввод отменен: активное окно больше не "
                    f"соответствует приложению '{clean_app_name}'. "
                    f"Текущее окно: '{active_title or 'неизвестно'}'."
                ),
            )


        typing_result = str(
            self.type_text(clean_text)
        )

        if self._result_failed(typing_result):
            return ToolResult.failure(
                "TEXT_INPUT_FAILED",
                typing_result,
            )

        return ToolResult.ok(
            (
                f"Текст введен в приложение "
                f"'{clean_app_name}'."
            ),
            data={
                "application": clean_app_name,
                "characters_written": len(clean_text),
                "new_document_requested": create_new_document,
                "launch_result": launch_message,
                "focus_result": focus_result,
                # Это подтверждает отправку ввода, но не чтение
                # содержимого обратно из редактора.
                "content_visually_verified": False,
            },
        )
