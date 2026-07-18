# tests/test_obsidian.py
from __future__ import annotations

import tempfile
from pathlib import Path

from modules.integrations.obsidian import (
    ObsidianVault,
    create_obsidian_note,
    append_obsidian_note,
    detect_obsidian_vaults,
    find_vault_by_name,
)


def test_obsidian_vault_dataclass() -> None:
    """Test ObsidianVault dataclass."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = ObsidianVault(
            path=Path(tmpdir),
            name="test_vault",
        )
        assert vault.name == "test_vault"
        assert str(vault.path) == tmpdir


def test_create_obsidian_note() -> None:
    """Test creating an Obsidian note."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = ObsidianVault(
            path=Path(tmpdir),
            name="test_vault",
        )

        result = create_obsidian_note(
            vault=vault,
            title="Тестовая заметка",
            content="Содержимое заметки",
        )

        assert result["success"] is True
        assert "path" in result
        assert result["title"] == "Тестовая заметка"

        # Verify file exists
        note_path = Path(result["path"])
        assert note_path.exists()
        assert note_path.read_text(encoding="utf-8") == "Содержимое заметки"


def test_create_obsidian_note_with_folder() -> None:
    """Test creating an Obsidian note in a subfolder."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = ObsidianVault(
            path=Path(tmpdir),
            name="test_vault",
        )

        result = create_obsidian_note(
            vault=vault,
            title="Заметка в папке",
            content="Содержимое",
            folder="Проекты",
        )

        assert result["success"] is True
        assert "Проекты" in result["path"]


def test_append_obsidian_note() -> None:
    """Test appending to an existing Obsidian note."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = ObsidianVault(
            path=Path(tmpdir),
            name="test_vault",
        )

        # Create initial note
        create_obsidian_note(
            vault=vault,
            title="Исходная",
            content="Первоначальное содержимое",
        )

        # Append to it
        result = append_obsidian_note(
            vault=vault,
            title="Исходная",
            content="Добавленное содержимое",
        )

        assert result["success"] is True

        # Verify content
        note_path = vault.path / "Исходная.md"
        content = note_path.read_text(encoding="utf-8")
        assert "Первоначальное содержимое" in content
        assert "Добавленное содержимое" in content


def test_append_nonexistent_note() -> None:
    """Test appending to a non-existent note."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = ObsidianVault(
            path=Path(tmpdir),
            name="test_vault",
        )

        result = append_obsidian_note(
            vault=vault,
            title="Не существует",
            content="Содержимое",
        )

        assert result["success"] is False
        assert result["code"] == "NOTE_NOT_FOUND"


def test_detect_obsidian_vaults_no_vaults(capsys: None) -> None:
    """Test vault detection when no vaults exist."""
    vaults = detect_obsidian_vaults()
    assert isinstance(vaults, list)