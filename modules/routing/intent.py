# modules/routing/intent.py
from __future__ import annotations

import re

from modules.input_hub.models import (
    UserRequest,
)
from modules.routing.decision import (
    ExecutionDecision,
    ExecutionStrategy,
    IntentKind,
)


KNOWN_APPLICATIONS = (
    "obsidian",
    "обсидиан",
    "блокнот",
    "notepad",
    "калькулятор",
    "calculator",
    "проводник",
    "explorer",
    "discord",
    "дискорд",
    "telegram",
    "телеграм",
    "chrome",
    "хром",
    "браузер",
    "visual studio code",
    "vs code",
    "вс код",
    "steam",
    "стим",
    "spotify",
    "спотифай",
)

CHAT_PHRASES = {
    "привет",
    "пока",
    "спасибо",
    "как дела",
    "что делаешь",
    "понятно",
    "ясно",
    "круто",
    "отлично",
    "хаха",
}

MODEL_SELECTION_MARKERS = (
    "переключись на модель",
    "используй модель",
    "быструю модель",
    "умную модель",
    "локальную модель",
    "только бесплатные модели",
    "автоматический выбор модели",
)

MODE_SELECTION_MARKERS = (
    "включи приватный режим",
    "выключи приватный режим",
    "текстовый режим",
    "голосовой режим",
    "непрерывный режим",
    "режим пробуждения",
    "режим инженера",
    "безопасный режим",
)

WRITE_MARKERS = (
    "напиши",
    "вставь",
    "введи",
    "напечатай",
    "создай заметку",
    "сделай заметку",
    "добавь текст",
)

TOPIC_MARKERS = (
    " о ",
    " про ",
    " с текстом ",
    " содержание ",
    " заголовок ",
    " стих ",
    " заметку ",
)

COMPLEX_MARKERS = (
    "сначала",
    "затем",
    "после этого",
    "после чего",
    "если успешно",
    "проверь результат",
    "выполни план",
    "сделай по шагам",
)

DEVELOPMENT_MARKERS = (
    "проект",
    "код",
    "тест",
    "pytest",
    "git",
    "docker",
    "kubernetes",
    "репозитор",
    "сервер",
    "рефактор",
    "ошибк",
    "traceback",
)

WEB_MARKERS = (
    "сайт",
    "интернет",
    "веб-страниц",
    "документац",
    "браузер",
    "url",
)


def normalize_request_text(
    text: str,
) -> str:
    normalized = str(text).lower()
    normalized = normalized.replace("ё", "е")
    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )
    return normalized.strip(" \t\r\n.!?")


def _contains_any(
    text: str,
    markers: tuple[str, ...],
) -> bool:
    return any(
        marker in text
        for marker in markers
    )


def _extract_application_name(
    text: str,
) -> str | None:
    for application in sorted(
        KNOWN_APPLICATIONS,
        key=len,
        reverse=True,
    ):
        if application in text:
            return application

    patterns = (
        r"(?:открой|запусти|включи)\s+"
        r"([a-zа-я0-9 _.-]{2,50})",
        r"(?:закрой|выключи|заверши)\s+"
        r"([a-zа-я0-9 _.-]{2,50})",
        r"(?:напиши|вставь|введи)\s+"
        r"(?:в|во)\s+([a-zа-я0-9 _.-]{2,50})",
    )

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        candidate = match.group(1)

        candidate = re.split(
            (
                r"\s+(?:и|а потом|затем|"
                r"после этого|напиши|сделай)"
            ),
            candidate,
            maxsplit=1,
        )[0]

        candidate = candidate.strip(
            " ,.!?:;"
        )

        if candidate:
            return candidate

    return None


def _requests_all_applications(
    text: str,
) -> bool:
    return any(
        marker in text
        for marker in (
            "все приложения",
            "всё приложения",
            "все программы",
            "все что можешь",
            "все, которые можешь",
            "каждое приложение",
        )
    )


def _has_content_or_topic(
    text: str,
) -> bool:
    return _contains_any(
        f" {text} ",
        TOPIC_MARKERS,
    )


class DeterministicIntentRouter:
    """
    Детерминированный skill-first роутер.

    Этот модуль не выполняет инструменты. Он только определяет
    наиболее эффективную стратегию выполнения.
    """

    def route(
        self,
        request: UserRequest | str,
        *,
        has_image: bool | None = None,
    ) -> ExecutionDecision:
        if isinstance(request, UserRequest):
            raw_text = request.text
            request_has_image = (
                request.has_image
            )
        else:
            raw_text = str(request)
            request_has_image = False

        if has_image is None:
            has_image = request_has_image

        text = normalize_request_text(
            raw_text
        )

        if not text and not has_image:
            return ExecutionDecision.clarify(
                "Что нужно сделать?",
                reason="Пустой запрос.",
            )

        if has_image:
            return ExecutionDecision(
                strategy=ExecutionStrategy.PLAN,
                intent=IntentKind.VISION,
                required_tools={
                    "get_active_window_ui_tree",
                    "find_ui_element",
                    "ocr_screen",
                    "find_text_on_screen",
                },
                needs_model=True,
                needs_tools=True,
                expected_model_calls=1,
                expected_tool_calls=1,
                confidence=0.95,
                reason=(
                    "Запрос содержит изображение."
                ),
            )

        if text in CHAT_PHRASES:
            return ExecutionDecision.chat(
                reason=(
                    "Распознана короткая чатовая фраза."
                )
            )

        if _contains_any(
            text,
            MODEL_SELECTION_MARKERS,
        ):
            return ExecutionDecision(
                strategy=ExecutionStrategy.DIRECT,
                intent=IntentKind.MODEL_SELECTION,
                needs_model=False,
                needs_tools=False,
                expected_model_calls=0,
                expected_tool_calls=0,
                confidence=0.98,
                reason=(
                    "Локальная команда выбора модели."
                ),
                metadata={
                    "raw_text": raw_text,
                },
            )

        if _contains_any(
            text,
            MODE_SELECTION_MARKERS,
        ):
            return ExecutionDecision(
                strategy=ExecutionStrategy.DIRECT,
                intent=IntentKind.MODE_SELECTION,
                needs_model=False,
                needs_tools=False,
                expected_model_calls=0,
                expected_tool_calls=0,
                confidence=0.98,
                reason=(
                    "Локальная команда выбора режима."
                ),
                metadata={
                    "raw_text": raw_text,
                },
            )

        if _requests_all_applications(text):
            return ExecutionDecision.clarify(
                (
                    "Запуск всех приложений может перегрузить "
                    "систему. Какие именно приложения открыть?"
                ),
                intent=IntentKind.APPLICATION_BATCH,
                reason=(
                    "Массовый запуск без ограниченного списка "
                    "небезопасен и неэффективен."
                ),
            )

        if any(
            marker in text
            for marker in (
                "сколько времени",
                "который час",
                "точное время",
            )
        ):
            return ExecutionDecision(
                strategy=ExecutionStrategy.DIRECT,
                intent=IntentKind.SYSTEM_TIME,
                required_tools={
                    "get_current_time",
                },
                needs_model=False,
                needs_tools=True,
                expected_model_calls=0,
                expected_tool_calls=1,
                reason="Прямая команда времени.",
            )

        if any(
            marker in text
            for marker in (
                "громкость",
                "сделай громче",
                "сделай тише",
                "выключи звук",
                "включи звук",
            )
        ):
            return ExecutionDecision(
                strategy=ExecutionStrategy.DIRECT,
                intent=IntentKind.SYSTEM_VOLUME,
                required_tools={
                    "change_volume",
                },
                needs_model=False,
                needs_tools=True,
                expected_model_calls=0,
                expected_tool_calls=1,
                reason="Прямая команда громкости.",
            )

        application_name = (
            _extract_application_name(text)
        )

        has_write_intent = _contains_any(
            text,
            WRITE_MARKERS,
        )

        if (
            application_name
            and has_write_intent
        ):
            if not _has_content_or_topic(text):
                return ExecutionDecision.clarify(
                    (
                        "Какой текст или тему нужно "
                        f"записать в {application_name}?"
                    ),
                    intent=(
                        IntentKind.APPLICATION_WRITE
                    ),
                    reason=(
                        "Указано приложение, но отсутствует "
                        "содержание или тема."
                    ),
                )

            return ExecutionDecision(
                strategy=ExecutionStrategy.SKILL,
                intent=IntentKind.APPLICATION_WRITE,
                required_tools={
                    "write_in_application",
                },
                selected_skill=(
                    "write_in_application"
                ),
                arguments={
                    "app_name": application_name,
                },
                needs_model=True,
                needs_tools=True,
                expected_model_calls=1,
                expected_tool_calls=1,
                confidence=0.95,
                reason=(
                    "Запись в приложение должна выполняться "
                    "одним высокоуровневым skill."
                ),
            )

        if (
            application_name
            and re.search(
                r"\b(?:открой|запусти|включи)\b",
                text,
            )
        ):
            return ExecutionDecision(
                strategy=ExecutionStrategy.DIRECT,
                intent=IntentKind.APPLICATION_OPEN,
                required_tools={
                    "open_application",
                },
                selected_skill=(
                    "open_application"
                ),
                arguments={
                    "app_name": application_name,
                },
                needs_model=False,
                needs_tools=True,
                expected_model_calls=0,
                expected_tool_calls=1,
                confidence=0.95,
                reason="Прямой запуск приложения.",
            )

        if (
            application_name
            and re.search(
                r"\b(?:закрой|выключи|заверши)\b",
                text,
            )
        ):
            return ExecutionDecision(
                strategy=ExecutionStrategy.DIRECT,
                intent=IntentKind.APPLICATION_CLOSE,
                required_tools={
                    "close_application",
                },
                selected_skill=(
                    "close_application"
                ),
                arguments={
                    "app_name": application_name,
                },
                needs_model=False,
                needs_tools=True,
                expected_model_calls=0,
                expected_tool_calls=1,
                confidence=0.95,
                reason="Прямое закрытие приложения.",
            )

        if _contains_any(
            text,
            DEVELOPMENT_MARKERS,
        ):
            strategy = (
                ExecutionStrategy.PLAN
                if _contains_any(
                    text,
                    COMPLEX_MARKERS,
                )
                else ExecutionStrategy.SKILL
            )

            return ExecutionDecision(
                strategy=strategy,
                intent=IntentKind.DEVELOPMENT,
                required_tools={
                    "inspect_project",
                    "git_status",
                    "run_terminal_command",
                    "start_process",
                    "read_process_output",
                    "apply_text_patch",
                },
                needs_model=True,
                needs_tools=True,
                expected_model_calls=(
                    2
                    if strategy
                    == ExecutionStrategy.PLAN
                    else 1
                ),
                expected_tool_calls=4,
                confidence=0.85,
                reason=(
                    "Инженерная задача требует анализа "
                    "или плана."
                ),
            )

        if _contains_any(
            text,
            WEB_MARKERS,
        ):
            return ExecutionDecision(
                strategy=ExecutionStrategy.SKILL,
                intent=IntentKind.WEB,
                required_tools={
                    "browser_open_url",
                    "browser_get_page_text",
                    "browser_click",
                    "browser_fill",
                    "browser_screenshot",
                },
                needs_model=True,
                needs_tools=True,
                expected_model_calls=1,
                expected_tool_calls=2,
                confidence=0.85,
                reason="Веб-задача.",
            )

        if _contains_any(
            text,
            COMPLEX_MARKERS,
        ):
            return ExecutionDecision(
                strategy=ExecutionStrategy.PLAN,
                intent=IntentKind.UNKNOWN_ACTION,
                required_tools={
                    "execute_plan",
                },
                needs_model=True,
                needs_tools=True,
                expected_model_calls=1,
                expected_tool_calls=1,
                confidence=0.7,
                reason=(
                    "Обнаружены признаки многошаговой задачи."
                ),
            )

        if re.search(
            (
                r"\b(?:сделай|создай|запусти|"
                r"удали|перемести|исправь)\b"
            ),
            text,
        ):
            return ExecutionDecision(
                strategy=ExecutionStrategy.SKILL,
                intent=IntentKind.UNKNOWN_ACTION,
                needs_model=True,
                needs_tools=True,
                expected_model_calls=1,
                expected_tool_calls=1,
                confidence=0.55,
                reason=(
                    "Обнаружен запрос действия, но прямой "
                    "intent не определён."
                ),
            )

        return ExecutionDecision.chat(
            reason=(
                "Запрос не требует системного действия."
            )
        )
