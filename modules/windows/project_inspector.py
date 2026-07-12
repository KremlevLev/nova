# modules/windows/project_inspector.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from modules.domain.results import ToolResult


logger = logging.getLogger("ProjectInspector")


def inspect_project(
    project_path: str,
) -> ToolResult:
    try:
        resolved = Path(project_path).resolve()

        if not resolved.is_dir():
            return ToolResult.failure(
                "DIRECTORY_NOT_FOUND",
                f"Каталог не найден: {resolved}",
            )

        info: dict[str, Any] = {
            "path": str(resolved),
            "name": resolved.name,
            "type": "unknown",
            "has_git": False,
            "has_docker": False,
            "has_ci": False,
            "languages": [],
            "package_managers": [],
            "entry_points": [],
            "test_frameworks": [],
            "config_files": [],
        }

        # Проверка Git.
        git_dir = resolved / ".git"
        info["has_git"] = git_dir.is_dir()

        # Проверка Docker.
        if (resolved / "Dockerfile").exists():
            info["has_docker"] = True
            info["config_files"].append(
                "Dockerfile"
            )

        if (resolved / "docker-compose.yml").exists():
            info["has_docker"] = True
            info["config_files"].append(
                "docker-compose.yml"
            )

        # Проверка CI.
        github_actions = (
            resolved
            / ".github"
            / "workflows"
        )
        if github_actions.is_dir():
            info["has_ci"] = True

        # Python.
        if (resolved / "requirements.txt").exists():
            info["type"] = "python"
            info["languages"].append("python")
            info["package_managers"].append("pip")
            info["config_files"].append(
                "requirements.txt"
            )

        if (resolved / "pyproject.toml").exists():
            info["type"] = "python"
            info["languages"].append("python")
            info["package_managers"].append("poetry")
            info["config_files"].append(
                "pyproject.toml"
            )

        if (resolved / "setup.py").exists():
            info["type"] = "python"
            info["languages"].append("python")
            info["config_files"].append("setup.py")

        # Node.js.
        if (resolved / "package.json").exists():
            info["type"] = "nodejs"
            info["languages"].append("javascript")
            info["package_managers"].append("npm")
            info["config_files"].append(
                "package.json"
            )

        # Go.
        if (resolved / "go.mod").exists():
            info["type"] = "go"
            info["languages"].append("go")
            info["config_files"].append("go.mod")

        # Rust.
        if (resolved / "Cargo.toml").exists():
            info["type"] = "rust"
            info["languages"].append("rust")
            info["config_files"].append(
                "Cargo.toml"
            )

        # Тестовые фреймворки.
        if (resolved / "pytest.ini").exists() or (
            resolved / "pyproject.toml"
        ).exists():
            try:
                content = (
                    resolved / "pyproject.toml"
                ).read_text()
                if "pytest" in content:
                    info["test_frameworks"].append(
                        "pytest"
                    )
            except Exception:
                pass

        if (resolved / "jest.config.js").exists():
            info["test_frameworks"].append("jest")

        # Точки входа.
        main_py = resolved / "main.py"
        if main_py.exists():
            info["entry_points"].append(
                "main.py"
            )

        app_py = resolved / "app.py"
        if app_py.exists():
            info["entry_points"].append("app.py")

        index_js = resolved / "index.js"
        if index_js.exists():
            info["entry_points"].append(
                "index.js"
            )

        # Уникальные значения.
        info["languages"] = list(
            dict.fromkeys(info["languages"])
        )
        info["package_managers"] = list(
            dict.fromkeys(
                info["package_managers"]
            )
        )
        info["test_frameworks"] = list(
            dict.fromkeys(
                info["test_frameworks"]
            )
        )
        info["config_files"] = list(
            dict.fromkeys(
                info["config_files"]
            )
        )

        return ToolResult.ok(
            f"Проект '{resolved.name}' проинспектирован. "
            f"Тип: {info['type']}.",
            data=info,
        )

    except PermissionError as exc:
        return ToolResult.failure(
            "INSPECT_PERMISSION_DENIED",
            f"Нет доступа к каталогу: {exc}",
        )
    except OSError as exc:
        return ToolResult.failure(
            "INSPECT_ERROR",
            f"Ошибка инспекции: {exc}",
        )
