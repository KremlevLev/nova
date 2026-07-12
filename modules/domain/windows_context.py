# modules/domain/windows_context.py
from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(slots=True)
class WindowsContextSnapshot:
    last_application: str | None = None
    last_window_title: str | None = None


class WindowsContext:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._last_application: str | None = None
        self._last_window_title: str | None = None

    def set_application(
        self,
        application_name: str,
    ) -> None:
        clean_name = application_name.strip()

        if not clean_name:
            return

        with self._lock:
            self._last_application = clean_name

    def set_window_title(
        self,
        window_title: str,
    ) -> None:
        clean_title = window_title.strip()

        if not clean_title:
            return

        with self._lock:
            self._last_window_title = clean_title

    def snapshot(self) -> WindowsContextSnapshot:
        with self._lock:
            return WindowsContextSnapshot(
                last_application=self._last_application,
                last_window_title=self._last_window_title,
            )

    def resolve_reference(
        self,
        user_text: str,
    ) -> str:
        text = user_text.strip()
        lowered = text.lower()

        reference_markers = (
            " там ",
            " туда ",
            " в нем ",
            " в ней ",
            " в это приложение ",
            " в этой программе ",
        )

        padded = f" {lowered} "

        if not any(
            marker in padded
            for marker in reference_markers
        ):
            return text

        snapshot = self.snapshot()

        if not snapshot.last_application:
            return text

        return (
            f"{text}\n\n"
            "[Локальный контекст Windows: "
            f"последнее успешно открытое приложение — "
            f"{snapshot.last_application}. "
            "Слова «там», «туда», «в нем» относятся к нему.]"
        )
