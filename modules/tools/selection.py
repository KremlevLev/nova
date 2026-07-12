# modules/tools/selection.py
from __future__ import annotations


COMMON_READ_TOOLS = {
    "get_current_time",
    "get_system_status",
    "search_in_memory",
    "get_active_reminders",
}

APPLICATION_TOOLS = {
    "open_application",
    "close_application",
    "list_active_windows",
    "focus_window",
}
HIGH_LEVEL_APPLICATION_SKILLS = {
    "write_in_application",
}

TEXT_INPUT_TOOLS = {
    "focus_window",
    "press_keyboard_combination",
    "type_text",
    "set_clipboard_content",
}

GUI_TOOLS = {
    "list_active_windows",
    "focus_window",
    "mouse_click",
    "press_keyboard_combination",
    "type_text",
}

WEB_TOOLS = {
    "search_web_tavily",
    "scrape_webpage",
    "open_website",
}

MEMORY_TOOLS = {
    "save_to_memory",
    "search_in_memory",
}

REMINDER_TOOLS = {
    "set_reminder",
    "get_active_reminders",
    "set_timer",
}

SYSTEM_TOOLS = {
    "change_volume",
    "manage_media",
    "manage_windows",
    "get_system_status",
}

DEVELOPMENT_TOOLS = {
    "create_workspace_project",
    "run_terminal_command",
    "execute_python_code",
    "get_clipboard_content",
    "set_clipboard_content",
}

NOTE_TOOLS = {
    "create_quick_note",
    "set_clipboard_content",
}

MODEL_DIAGNOSTIC_TOOLS = {
    "get_model_provider_status",
}


def contains_any(
    text: str,
    markers: tuple[str, ...],
) -> bool:
    return any(marker in text for marker in markers)


def select_tool_names(
    user_text: str,
    *,
    has_image: bool,
) -> set[str]:
    """
    Возвращает только те инструменты, которые относятся к запросу.

    Это не security boundary: окончательное решение все равно принимает
    ToolRunner и policy layer. Функция уменьшает контекст модели и число
    ошибочных tool calls.
    """
    text = user_text.lower().replace("ё", "е")
    selected = set(COMMON_READ_TOOLS)
    filesystem_markers = (
        "файл",
        "прочитай файл",
        "открой файл",
        "сохрани файл",
        "запиши файл",
        "создай файл",
        "найди файл",
        "поиск файлов",
        "дифф",
        "diff",
        "патч",
        "patch",
        "откати",
        "rollback",
        "восстанови файл",
    )
    memory_store_markers = (
        "запомни",
        "сохрани в память",
        "найди в памяти",
        "удали из памяти",
        "очисти память",
        "что ты помнишь",
    )

    if contains_any(text, memory_store_markers):
        selected |= MEMORY_STORE_TOOLS

    git_markers = (
        "git",
        "коммит",
        "commit",
        "ветк",
        "branch",
        "статус репозитория",
        "история коммитов",
        "пулл",
        "pull",
        "пуш",
        "push",
    )
    artifact_markers = (
        "артефакт",
        "сохрани результат",
        "сохрани лог",
        "прочитай артефакт",
    )

    if contains_any(text, artifact_markers):
        selected |= ARTIFACT_TOOLS

    project_markers = (
        "проект",
        "инспектир",
        "inspect",
        "структура проекта",
        "тип проекта",
        "docker",
        "докер",
    )

    if contains_any(text, git_markers):
        selected |= GIT_TOOLS

    if contains_any(text, project_markers):
        selected |= PROJECT_TOOLS

    if contains_any(text, filesystem_markers):
        selected |= FILESYSTEM_TOOLS

    application_markers = (
        "открой",
        "запусти",
        "включи",
        "закрой",
        "выключи",
        "приложен",
        "программ",
        "окно",
        "обсидиан",
        "obsidian",
        "блокнот",
        "notepad",
        "дискорд",
        "discord",
        "телеграм",
        "telegram",
        "хром",
        "chrome",
        "браузер",
        "вс код",
        "visual studio code",
        "калькулятор",
        "проводник",
    )

    text_input_markers = (
        "напиши",
        "вставь",
        "напечатай",
        "введи",
        "текст",
        "заметк",
        "стих",
        "сохрани",
        "создай документ",
        "новый файл",
    )

    web_markers = (
        "интернет",
        "найди в сети",
        "поищи в сети",
        "сайт",
        "страниц",
        "документац",
        "ссылка",
        "url",
        "новости",
    )

    memory_markers = (
        "запомни",
        "помнишь",
        "в памяти",
        "предпочт",
        "забудь",
    )
    development_markers = (
        "код",
        "скрипт",
        "проект",
        "терминал",
        "команд",
        "тест",
        "pytest",
        "pip",
        "git",
        "docker",
        "kubernetes",
        "python",
        "traceback",
        "репозитор",
        "fastapi",
        "сервер",
        "база данных",
        "логи",
        "запусти сервер",
        "запусти тесты",
        "фоновый процесс",
        "процесс",
    )

    if contains_any(text, development_markers):
        selected |= DEVELOPMENT_TOOLS
        selected |= PROCESS_MANAGER_TOOLS

    reminder_markers = (
        "напомни",
        "напоминан",
        "таймер",
        "будильник",
    )

    system_markers = (
        "громкость",
        "звук",
        "громче",
        "тише",
        "музык",
        "трек",
        "пауза",
        "сверни окна",
        "сверни все окна",
    )

    development_markers = (
        "код",
        "скрипт",
        "проект",
        "терминал",
        "команд",
        "тест",
        "pytest",
        "pip",
        "git",
        "docker",
        "kubernetes",
        "python",
        "traceback",
        "репозитор",
        "fastapi",
        "сервер",
        "база данных",
        "логи",
    )

    note_markers = (
        "быструю заметку",
        "заметку на рабочем столе",
        "сохрани идею",
    )

    provider_markers = (
        "статус моделей",
        "статус провайдеров",
        "какой ключ",
        "groq",
        "openrouter",
        "лимит модели",
    )

    if contains_any(text, application_markers):
        selected |= APPLICATION_TOOLS

    if contains_any(text, text_input_markers):
        selected |= HIGH_LEVEL_APPLICATION_SKILLS

    # Оставляем инструменты наблюдения, но не выдаем модели
    # ручную цепочку focus -> hotkey -> type_text.
        selected |= {
        "open_application",
        "list_active_windows",
    }


    if contains_any(text, web_markers):
        selected |= WEB_TOOLS

    if contains_any(text, memory_markers):
        selected |= MEMORY_TOOLS

    if contains_any(text, reminder_markers):
        selected |= REMINDER_TOOLS

    if contains_any(text, system_markers):
        selected |= SYSTEM_TOOLS

    if contains_any(text, development_markers):
        selected |= DEVELOPMENT_TOOLS

    if contains_any(text, note_markers):
        selected |= NOTE_TOOLS

    if contains_any(text, provider_markers):
        selected |= MODEL_DIAGNOSTIC_TOOLS

    if has_image:
        selected |= GUI_TOOLS

    return selected
PROCESS_MANAGER_TOOLS = {
    "start_process",
    "get_process_status",
    "read_process_output",
    "stop_process",
    "list_processes",
}
FILESYSTEM_TOOLS = {
    "read_text_file",
    "write_text_file",
    "apply_text_patch",
    "get_file_diff",
    "search_files",
    "rollback_file",
}

GIT_TOOLS = {
    "git_status",
    "git_diff",
    "git_log",
    "git_commit",
    "git_branch",
}

PROJECT_TOOLS = {
    "inspect_project",
}

MEMORY_STORE_TOOLS = {
    "save_memory",
    "search_memory",
    "delete_memory",
    "clear_all_memories",
}
ARTIFACT_TOOLS = {
    "store_artifact",
    "read_artifact",
    "delete_artifact",
}
