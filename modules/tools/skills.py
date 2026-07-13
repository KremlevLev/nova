# modules/tools/skills.py
from __future__ import annotations

import logging
import time
from typing import Callable

from modules.domain.results import (
    ToolResult,
    VerificationResult,
)
from modules.tools.app_indexer import (
    WindowsAppIndexer,
    normalize_app_name,
    get_visible_window_titles,
)


logger = logging.getLogger("Skills")


class WindowsSkills:
    """
    Высокоуровневые Windows-навыки Nova.

    Каждый навык объединяет несколько атомарных операций
    в один вызов с проверкой результата.
    """

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
        self.get_active_window_title = get_active_window_title

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
        """
        Открывает приложение, фокусирует окно, создаёт новый документ
        и вводит текст. Проверяет активное окно перед вводом.
        """
        clean_app_name = app_name.strip()
        clean_text = text.strip()

        if not clean_app_name:
            return ToolResult.failure("EMPTY_APPLICATION_NAME", "Название приложения не указано.")

        if not clean_text:
            return ToolResult.failure("EMPTY_TEXT", "Текст для записи не указан.")

        if len(clean_text) > 100_000:
            return ToolResult.failure("TEXT_TOO_LARGE", "За один вызов разрешено ввести до 100000 символов.")

        # Шаг 1: запуск приложения.
        launch_success, launch_message = self.app_launcher.launch_by_name(clean_app_name)

        if not launch_success:
            return ToolResult.failure("APPLICATION_LAUNCH_FAILED", launch_message)

        # Даем приложению время на активацию окна.
        time.sleep(0.8)

        # Шаг 2: фокусировка окна.
        focus_result = str(self.focus_window(clean_app_name))

        if self._result_failed(focus_result):
            match = self.app_launcher.find_app(clean_app_name)

            if match is not None:
                focus_result = str(self.focus_window(match.matched_name))

        if self._result_failed(focus_result):
            return ToolResult.failure(
                "WINDOW_FOCUS_FAILED",
                f"Приложение запущено, но его окно не удалось сфокусировать: {focus_result}",
                data={"launch_message": launch_message},
            )

        # Шаг 3: создание нового документа.
        if create_new_document:
            hotkey_result = str(self.press_hotkey("ctrl+n"))

            if self._result_failed(hotkey_result):
                return ToolResult.failure(
                    "NEW_DOCUMENT_FAILED",
                    f"Окно сфокусировано, но не удалось создать новый документ: {hotkey_result}",
                )

            time.sleep(0.3)

        # Шаг 4: проверка активного окна перед вводом.
        active_title = str(self.get_active_window_title()).strip()
        match = self.app_launcher.find_app(clean_app_name)

        expected_names = {clean_app_name.lower()}

        if match is not None:
            expected_names.add(match.matched_name.lower())

        if not active_title or not any(expected_name in active_title.lower() for expected_name in expected_names):
            return ToolResult.failure(
                "ACTIVE_WINDOW_CHANGED",
                f"Ввод отменен: активное окно больше не соответствует приложению '{clean_app_name}'. Текущее окно: '{active_title or 'неизвестно'}'.",
            )

        # Шаг 5: ввод текста.
        typing_result = str(self.type_text(clean_text))

        if self._result_failed(typing_result):
            return ToolResult.failure("TEXT_INPUT_FAILED", typing_result)

        return ToolResult.ok(
            f"Текст введен в приложение '{clean_app_name}'.",
            data={
                "application": clean_app_name,
                "characters_written": len(clean_text),
                "new_document_requested": create_new_document,
                "launch_result": launch_message,
                "focus_result": focus_result,
                "content_visually_verified": False,
            },
            verification=VerificationResult(
                verified=True,
                method="window_check_and_type",
                confidence=0.9,
                details="Окно проверено, текст отправлен.",
            ),
        )

    def open_and_focus(
        self,
        app_name: str,
    ) -> ToolResult:
        """
        Открывает приложение и фокусирует его окно.
        """
        clean_app_name = app_name.strip()

        if not clean_app_name:
            return ToolResult.failure("EMPTY_APPLICATION_NAME", "Название приложения не указано.")

        launch_success, launch_message = self.app_launcher.launch_by_name(clean_app_name)

        if not launch_success:
            return ToolResult.failure("APPLICATION_LAUNCH_FAILED", launch_message)

        time.sleep(0.5)

        focus_result = str(self.focus_window(clean_app_name))

        if self._result_failed(focus_result):
            match = self.app_launcher.find_app(clean_app_name)

            if match is not None:
                focus_result = str(self.focus_window(match.matched_name))

        if self._result_failed(focus_result):
            return ToolResult.failure(
                "WINDOW_FOCUS_FAILED",
                f"Приложение запущено, но окно не сфокусировано: {focus_result}",
            )

        return ToolResult.ok(
            f"Приложение '{clean_app_name}' открыто и сфокусировано.",
            data={
                "application": clean_app_name,
                "launch_result": launch_message,
                "focus_result": focus_result,
            },
        )
