# modules/integrations/obsidian.py
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import Any

import logging

logger = logging.getLogger("ObsidianAdapter")


@dataclass
class ObsidianVault:
    path: Path
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path):
            self.path = Path(self.path)


def detect_obsidian_vaults() -> list[ObsidianVault]:
    """
    Находит все Obsidian vault'ы на системе.

    Ищет папки с .obsidian подпапкой.
    """
    vaults: list[ObsidianVault] = []

    # Обычные места для vault'ов
    search_roots = [
        Path.home() / "Documents",
        Path.home() / "Obsidian",
        Path.home(),  # На случай если vault в home
    ]

    for root in search_roots:
        if not root.exists():
            continue

        try:
            for item in root.iterdir():
                if item.is_dir():
                    obsidian_dir = item / ".obsidian"
                    if obsidian_dir.exists() and obsidian_dir.is_dir():
                        vaults.append(
                            ObsidianVault(
                                path=item,
                                name=item.name,
                            )
                        )
        except (PermissionError, OSError):
            continue

    return vaults


def find_vault_by_name(
    name: str | None = None,
    path: str | None = None,
) -> ObsidianVault | None:
    """
    Находит vault по имени или пути.
    """
    if path:
        vault_path = Path(path)
        if (vault_path / ".obsidian").exists():
            return ObsidianVault(
                path=vault_path,
                name=vault_path.name,
            )
        return None

    if name:
        for vault in detect_obsidian_vaults():
            if vault.name.lower() == name.lower():
                return vault

    # Возвращаем первый найденный vault
    vaults = detect_obsidian_vaults()
    return vaults[0] if vaults else None


def create_obsidian_note(
    vault: ObsidianVault,
    title: str,
    content: str,
    folder: str | None = None,
) -> dict[str, Any]:
    """
    Создаёт заметку в Obsidian vault.

    Возвращает:
    - success: bool
    - path: str (путь к файлу)
    - artifact_id: str (для хранения в ArtifactStore)
    """
    try:
        if folder:
            note_dir = vault.path / folder
            note_dir.mkdir(parents=True, exist_ok=True)
        else:
            note_dir = vault.path

        # Нормализуем имя файла
        safe_title = re.sub(r'[<>:"/\\|?*]', "", title)
        safe_title = safe_title.strip() or "Без названия"

        note_path = note_dir / f"{safe_title}.md"

        # Записываем файл атомарно
        note_path.write_text(
            content,
            encoding="utf-8",
        )

        artifact_id = f"obsidian_note_{uuid.uuid4().hex}"

        return {
            "success": True,
            "message": f"Создана заметка: {safe_title}",
            "path": str(note_path),
            "title": safe_title,
            "artifact_id": artifact_id,
            "data": {
                "vault": vault.name,
                "folder": folder,
            },
        }

    except Exception as exc:
        logger.exception(
            "Не удалось создать заметку в Obsidian: %s",
            exc,
        )
        return {
            "success": False,
            "code": "OBSIDIAN_NOTE_FAILED",
            "message": f"Не удалось создать заметку: {exc}",
            "data": {
                "vault": vault.name,
                "title": title,
            },
        }


def append_obsidian_note(
    vault: ObsidianVault,
    title: str,
    content: str,
) -> dict[str, Any]:
    """
    Добавляет содержимое в существующую заметку.
    """
    try:
        safe_title = re.sub(r'[<>:"/\\|?*]', "", title)
        note_path = vault.path / f"{safe_title}.md"

        if not note_path.exists():
            return {
                "success": False,
                "code": "NOTE_NOT_FOUND",
                "message": f"Заметка не найдена: {safe_title}",
            }

        existing_content = note_path.read_text(encoding="utf-8")
        updated_content = existing_content + "\n\n" + content

        note_path.write_text(
            updated_content,
            encoding="utf-8",
        )

        return {
            "success": True,
            "message": f"Добавлено в заметку: {safe_title}",
            "path": str(note_path),
            "title": safe_title,
        }

    except Exception as exc:
        logger.exception(
            "Не удалось дописать заметку: %s",
            exc,
        )
        return {
            "success": False,
            "code": "OBSIDIAN_APPEND_FAILED",
            "message": f"Не удалось дописать заметку: {exc}",
        }


def open_obsidian_uri(
    vault: ObsidianVault,
    note_path: str | None = None,
) -> dict[str, Any]:
    """
    Открывает Obsidian через obsidian:// URI.
    """
    try:
        import webbrowser

        if note_path:
            uri = f"obsidian://open?vault={vault.name}&file={note_path}"
        else:
            uri = f"obsidian://open?vault={vault.name}"

        webbrowser.open(uri)

        return {
            "success": True,
            "message": f"Открыт vault: {vault.name}",
            "uri": uri,
        }

    except Exception as exc:
        logger.exception("Не удалось открыть Obsidian: %s", exc)
        return {
            "success": False,
            "code": "OBSIDIAN_OPEN_FAILED",
            "message": f"Не удалось открыть Obsidian: {exc}",
        }


def search_obsidian_notes(
    vault: ObsidianVault,
    query: str,
) -> list[dict[str, Any]]:
    """
    Поиск по содержимому заметок в vault.
    """
    results: list[dict[str, Any]] = []
    query_lower = query.lower()

    try:
        for md_file in vault.path.glob("**/*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    # Извлекаем первые 200 символов контекста
                    idx = content.lower().find(query_lower)
                    start = max(0, idx - 50)
                    end = min(len(content), idx + 250)

                    results.append({
                        "path": str(md_file.relative_to(vault.path)),
                        "title": md_file.stem,
                        "excerpt": content[start:end].strip(),
                    })
            except Exception:
                continue

    except Exception:
        pass

    return results


def create_daily_note(
    vault: ObsidianVault,
    content: str,
) -> dict[str, Any]:
    """
    Создаёт дневную заметку.
    """
    from datetime import datetime

    date_str = datetime.now().strftime("%Y-%m-%d")
    return create_obsidian_note(
        vault=vault,
        title=date_str,
        content=content,
    )


def add_obsidian_tags(
    vault: ObsidianVault,
    title: str,
    tags: list[str],
) -> dict[str, Any]:
    """
    Добавляет теги к заметке.
    """
    try:
        safe_title = re.sub(r'[<>:"/\\|?*]', "", title)
        note_path = vault.path / f"{safe_title}.md"

        if not note_path.exists():
            return {
                "success": False,
                "code": "NOTE_NOT_FOUND",
                "message": f"Заметка не найдена: {safe_title}",
            }

        content = note_path.read_text(encoding="utf-8")

        # Добавляем теги в начало файла
        tag_line = " ".join(f"#{tag.lstrip('#')}" for tag in tags)
        existing_tags = re.findall(r"#(\w+)", content[:500])

        new_tags = [
            f"#{tag}"
            for tag in tags
            if tag.lstrip('#') not in existing_tags
        ]

        if not new_tags:
            return {
                "success": True,
                "message": "Теги уже есть в заметке.",
            }

        tag_line = " ".join(new_tags)

        if content and not content.startswith("#"):
            new_content = f"{tag_line}\n\n{content}"
        else:
            new_content = content

        note_path.write_text(new_content, encoding="utf-8")

        return {
            "success": True,
            "message": f"Добавлены теги: {tag_line}",
            "tags": new_tags,
        }

    except Exception as exc:
        logger.exception("Не удалось добавить теги: %s", exc)
        return {
            "success": False,
            "code": "TAG_ADD_FAILED",
            "message": f"Не удалось добавить теги: {exc}",
        }


def list_obsidian_vaults_safe() -> list[dict[str, str]]:
    """
    Возвращает список vault'ов безопасным способом.
    """
    return [
        {"name": vault.name, "path": str(vault.path)}
        for vault in detect_obsidian_vaults()
    ]