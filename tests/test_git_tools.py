# tests/test_git_tools.py
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from modules.windows.git_tools import (
    git_status,
    git_diff,
    git_log,
    git_commit,
    git_branch,
)


def _init_git_repo(
    directory: Path,
) -> None:
    subprocess.run(
        ["git", "init"],
        cwd=str(directory),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(directory),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(directory),
        capture_output=True,
    )


def test_git_status_clean() -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        _init_git_repo(repo)

        result = git_status(str(repo))

        assert result.success
        assert "чист" in result.message.lower()


def test_git_status_with_changes() -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        _init_git_repo(repo)

        (repo / "test.txt").write_text("content")

        result = git_status(str(repo))

        assert result.success
        assert result.data["unstaged"]


def test_git_commit() -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        _init_git_repo(repo)

        (repo / "test.txt").write_text("content")

        result = git_commit(
            str(repo),
            "Initial commit",
        )

        assert result.success
        assert "Initial commit" in result.message


def test_git_log() -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        _init_git_repo(repo)

        (repo / "test.txt").write_text("content")
        git_commit(str(repo), "First commit")

        (repo / "test.txt").write_text("modified")
        git_commit(str(repo), "Second commit")

        result = git_log(str(repo))

        assert result.success
        assert len(result.data["commits"]) == 2


def test_git_branch() -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        _init_git_repo(repo)

        result = git_branch(str(repo))

        assert result.success
        assert result.data["branches"]
