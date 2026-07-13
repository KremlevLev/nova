# tests/test_skills_v2.py
from __future__ import annotations

from modules.tools.skills import WindowsSkills
from modules.tools.app_indexer import WindowsAppIndexer


def test_write_in_application_rejects_empty_app_name() -> None:
    skills = WindowsSkills(
        app_launcher=WindowsAppIndexer(),
        list_windows=lambda: "",
        focus_window=lambda x: "Окно сфокусировано.",
        press_hotkey=lambda x: "Комбинация нажата.",
        type_text=lambda x: "Текст введён.",
        get_active_window_title=lambda: "Obsidian",
    )

    result = skills.write_in_application(
        app_name="",
        text="test",
    )

    assert not result.success
    assert result.code == "EMPTY_APPLICATION_NAME"


def test_write_in_application_rejects_empty_text() -> None:
    skills = WindowsSkills(
        app_launcher=WindowsAppIndexer(),
        list_windows=lambda: "",
        focus_window=lambda x: "Окно сфокусировано.",
        press_hotkey=lambda x: "Комбинация нажата.",
        type_text=lambda x: "Текст введён.",
        get_active_window_title=lambda: "Obsidian",
    )

    result = skills.write_in_application(
        app_name="Obsidian",
        text="",
    )

    assert not result.success
    assert result.code == "EMPTY_TEXT"


def test_open_and_focus_rejects_empty_name() -> None:
    skills = WindowsSkills(
        app_launcher=WindowsAppIndexer(),
        list_windows=lambda: "",
        focus_window=lambda x: "Окно сфокусировано.",
        press_hotkey=lambda x: "Комбинация нажата.",
        type_text=lambda x: "Текст введён.",
        get_active_window_title=lambda: "",
    )

    result = skills.open_and_focus(app_name="")

    assert not result.success
    assert result.code == "EMPTY_APPLICATION_NAME"


def test_selection_includes_high_level_skills() -> None:
    from modules.tools.selection import select_tool_names

    result = select_tool_names(
        "Открой Obsidian и напиши стих",
        has_image=False,
    )

    assert "write_in_application" in result
    assert "open_and_focus" in result


def test_selection_includes_skills_for_complex_command() -> None:
    from modules.tools.selection import select_tool_names

    result = select_tool_names(
        "Включи обсидиан, сделай там заметку и напиши стих",
        has_image=False,
    )

    assert "write_in_application" in result
    assert "open_and_focus" in result
