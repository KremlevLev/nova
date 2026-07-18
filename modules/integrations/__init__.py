# modules/integrations/__init__.py
from __future__ import annotations

from modules.integrations.obsidian import (
    ObsidianVault,
    detect_obsidian_vaults,
    find_vault_by_name,
    create_obsidian_note,
    append_obsidian_note,
    open_obsidian_uri,
    search_obsidian_notes,
    create_daily_note,
    add_obsidian_tags,
    list_obsidian_vaults_safe,
)

__all__ = [
    "ObsidianVault",
    "detect_obsidian_vaults",
    "find_vault_by_name",
    "create_obsidian_note",
    "append_obsidian_note",
    "open_obsidian_uri",
    "search_obsidian_notes",
    "create_daily_note",
    "add_obsidian_tags",
    "list_obsidian_vaults_safe",
]