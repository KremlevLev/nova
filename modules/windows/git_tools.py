# modules/windows/git_tools.py
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from modules.domain.results import (
    ToolResult,
    VerificationResult,
)


logger = logging.getLogger("GitTools")


def _run_git_command(
    command: list[str],
    cwd: str | Path | None = None,
    *,
    timeout_seconds: float = 30.0,
) -> tuple[str, str, int]:
    try:
        result = subprocess.run(
            ["git"] + command,
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=timeout_seconds,
        )

        return (
            result.stdout.strip(),
            result.stderr.strip(),
            result.returncode,
        )

    except FileNotFoundError:
        raise RuntimeError(
            "Git не найден. Убедитесь, что Git установлен "
            "и доступен в PATH."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "Git-команда превысила лимит времени."
        )


def git_status(
    repo_path: str,
) -> ToolResult:
    try:
        resolved = Path(repo_path).resolve()

        if not resolved.is_dir():
            return ToolResult.failure(
                "DIRECTORY_NOT_FOUND",
                f"Каталог не найден: {resolved}",
            )

        stdout, stderr, returncode = _run_git_command(
            ["status", "--short"],
            cwd=resolved,
        )

        if returncode != 0:
            return ToolResult.failure(
                "GIT_ERROR",
                f"Ошибка Git: {stderr}",
            )

        if not stdout:
            return ToolResult.ok(
                f"Репозиторий '{resolved.name}' чист, "
                "нет изменений."
            )

        lines = stdout.splitlines()
        staged = [
            line[3:]
            for line in lines
            if line.startswith("M ") or line.startswith("A ")
        ]
        unstaged = [
            line[3:]
            for line in lines
            if line.startswith(" M") or line.startswith("??")
        ]

        return ToolResult.ok(
            f"Статус Git: {len(lines)} изменённых файлов.",
            data={
                "repo": str(resolved),
                "staged": staged,
                "unstaged": unstaged,
                "raw": stdout,
            },
        )

    except RuntimeError as exc:
        return ToolResult.failure(
            "GIT_ERROR",
            str(exc),
        )


def git_diff(
    repo_path: str,
    *,
    staged: bool = False,
) -> ToolResult:
    try:
        resolved = Path(repo_path).resolve()

        command = ["diff"]
        if staged:
            command.append("--cached")

        stdout, stderr, returncode = _run_git_command(
            command,
            cwd=resolved,
        )

        if returncode != 0:
            return ToolResult.failure(
                "GIT_ERROR",
                f"Ошибка Git: {stderr}",
            )

        if not stdout:
            return ToolResult.ok(
                "Нет изменений для отображения."
            )

        return ToolResult.ok(
            f"Diff репозитория '{resolved.name}':",
            data={
                "repo": str(resolved),
                "diff": stdout,
                "staged": staged,
            },
        )

    except RuntimeError as exc:
        return ToolResult.failure(
            "GIT_ERROR",
            str(exc),
        )


def git_log(
    repo_path: str,
    *,
    max_count: int = 10,
) -> ToolResult:
    try:
        resolved = Path(repo_path).resolve()

        stdout, stderr, returncode = _run_git_command(
            [
                "log",
                f"--max-count={max_count}",
                "--oneline",
                "--decorate",
            ],
            cwd=resolved,
        )

        if returncode != 0:
            return ToolResult.failure(
                "GIT_ERROR",
                f"Ошибка Git: {stderr}",
            )

        if not stdout:
            return ToolResult.ok(
                "В репозитории нет коммитов."
            )

        commits = stdout.splitlines()

        return ToolResult.ok(
            f"Последние {len(commits)} коммитов:",
            data={
                "repo": str(resolved),
                "commits": commits,
            },
        )

    except RuntimeError as exc:
        return ToolResult.failure(
            "GIT_ERROR",
            str(exc),
        )


def git_commit(
    repo_path: str,
    message: str,
    *,
    add_all: bool = True,
) -> ToolResult:
    try:
        resolved = Path(repo_path).resolve()

        if add_all:
            add_stdout, add_stderr, add_code = _run_git_command(
                ["add", "-A"],
                cwd=resolved,
            )

            if add_code != 0:
                return ToolResult.failure(
                    "GIT_ADD_ERROR",
                    f"Ошибка git add: {add_stderr}",
                )

        commit_stdout, commit_stderr, commit_code = (
            _run_git_command(
                ["commit", "-m", message],
                cwd=resolved,
            )
        )

        if commit_code != 0:
            return ToolResult.failure(
                "GIT_COMMIT_ERROR",
                f"Ошибка git commit: {commit_stderr}",
            )

        return ToolResult.ok(
            f"Коммит создан: {message}",
            data={
                "repo": str(resolved),
                "message": message,
                "output": commit_stdout,
            },
            verification=VerificationResult(
                verified=True,
                method="git_commit_success",
                confidence=1.0,
            ),
        )

    except RuntimeError as exc:
        return ToolResult.failure(
            "GIT_ERROR",
            str(exc),
        )


def git_branch(
    repo_path: str,
) -> ToolResult:
    try:
        resolved = Path(repo_path).resolve()

        stdout, stderr, returncode = _run_git_command(
            ["branch", "-a"],
            cwd=resolved,
        )

        if returncode != 0:
            return ToolResult.failure(
                "GIT_ERROR",
                f"Ошибка Git: {stderr}",
            )

        branches = [
            line.strip()
            for line in stdout.splitlines()
            if line.strip()
        ]

        return ToolResult.ok(
            f"Ветки репозитория '{resolved.name}':",
            data={
                "repo": str(resolved),
                "branches": branches,
            },
        )

    except RuntimeError as exc:
        return ToolResult.failure(
            "GIT_ERROR",
            str(exc),
        )
