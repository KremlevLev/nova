# tests/test_project_inspector.py
from __future__ import annotations

import tempfile
from pathlib import Path

from modules.windows.project_inspector import (
    inspect_project,
)


def test_inspect_python_project() -> None:
    with tempfile.TemporaryDirectory() as directory:
        project = Path(directory)

        (project / "requirements.txt").write_text(
            "requests\n"
        )
        (project / "main.py").write_text(
            "print('hello')"
        )

        result = inspect_project(str(project))

        assert result.success
        assert result.data["type"] == "python"
        assert "python" in result.data["languages"]
        assert "pip" in result.data[
            "package_managers"
        ]
        assert "main.py" in result.data[
            "entry_points"
        ]


def test_inspect_nodejs_project() -> None:
    with tempfile.TemporaryDirectory() as directory:
        project = Path(directory)

        (project / "package.json").write_text(
            '{"name": "test"}'
        )
        (project / "index.js").write_text(
            "console.log('hello')"
        )

        result = inspect_project(str(project))

        assert result.success
        assert result.data["type"] == "nodejs"
        assert "javascript" in result.data[
            "languages"
        ]
        assert "npm" in result.data[
            "package_managers"
        ]


def test_inspect_docker_project() -> None:
    with tempfile.TemporaryDirectory() as directory:
        project = Path(directory)

        (project / "Dockerfile").write_text(
            "FROM python:3.11"
        )

        result = inspect_project(str(project))

        assert result.success
        assert result.data["has_docker"]


def test_inspect_nonexistent_directory() -> None:
    result = inspect_project(
        "C:\\nonexistent_project_12345"
    )

    assert not result.success
    assert result.code == "DIRECTORY_NOT_FOUND"
