# tests/test_filesystem.py
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from modules.windows.filesystem import (
    read_text_file,
    write_text_file,
    apply_text_patch,
    get_file_diff,
    search_files,
    rollback_file,
)


def test_write_and_read_file() -> None:
    with tempfile.TemporaryDirectory() as directory:
        file_path = (
            Path(directory) / "test.txt"
        )

        write_result = write_text_file(
            str(file_path),
            "Hello, Nova!",
        )

        assert write_result.success
        assert write_result.data["size"] == 12

        read_result = read_text_file(
            str(file_path)
        )

        assert read_result.success
        assert (
            read_result.data["content"]
            == "Hello, Nova!"
        )


def test_write_creates_backup() -> None:
    with tempfile.TemporaryDirectory() as directory:
        file_path = (
            Path(directory) / "backup_test.txt"
        )

        write_text_file(
            str(file_path),
            "Original content",
        )

        write_result = write_text_file(
            str(file_path),
            "Modified content",
            create_backup=True,
        )

        assert write_result.success
        assert (
            "original_hash"
            in write_result.data
        )


def test_apply_patch_add_line() -> None:
    with tempfile.TemporaryDirectory() as directory:
        file_path = (
            Path(directory) / "patch_test.txt"
        )

        write_text_file(
            str(file_path),
            "Line 1\nLine 2\n",
        )

        patch_result = apply_text_patch(
            str(file_path),
            "+ Line 3",
        )

        assert patch_result.success

        read_result = read_text_file(
            str(file_path)
        )

        assert "Line 3" in (
            read_result.data["content"]
        )


def test_apply_patch_remove_line() -> None:
    with tempfile.TemporaryDirectory() as directory:
        file_path = (
            Path(directory) / "remove_test.txt"
        )

        write_text_file(
            str(file_path),
            "Keep this\nRemove this\nKeep this too",
        )

        patch_result = apply_text_patch(
            str(file_path),
            "- Remove this",
        )

        assert patch_result.success

        read_result = read_text_file(
            str(file_path)
        )

        assert "Remove this" not in (
            read_result.data["content"]
        )


def test_apply_patch_replace_line() -> None:
    with tempfile.TemporaryDirectory() as directory:
        file_path = (
            Path(directory) / "replace_test.txt"
        )

        write_text_file(
            str(file_path),
            "Old content",
        )

        patch_result = apply_text_patch(
            str(file_path),
            "= Old content -> New content",
        )

        assert patch_result.success

        read_result = read_text_file(
            str(file_path)
        )

        assert (
            read_result.data["content"]
            == "New content"
        )


def test_get_file_diff() -> None:
    with tempfile.TemporaryDirectory() as directory:
        file_path = (
            Path(directory) / "diff_test.txt"
        )

        write_text_file(
            str(file_path),
            "Line 1\nLine 2\nLine 3",
        )

        diff_result = get_file_diff(
            str(file_path)
        )

        assert diff_result.success
        assert "diff_test.txt" in (
            diff_result.data["diff"]
        )


def test_search_files() -> None:
    with tempfile.TemporaryDirectory() as directory:
        Path(directory, "file_a.py").write_text(
            "print('a')"
        )
        Path(directory, "file_b.py").write_text(
            "print('b')"
        )
        Path(
            directory, "readme.md"
        ).write_text("# Readme")

        search_result = search_files(
            directory,
            "*.py",
        )

        assert search_result.success
        assert search_result.data["count"] == 2


def test_rollback_file() -> None:
    with tempfile.TemporaryDirectory() as directory:
        file_path = (
            Path(directory) / "rollback_test.txt"
        )

        write_text_file(
            str(file_path),
            "Original",
        )

        write_text_file(
            str(file_path),
            "Modified",
            create_backup=True,
        )

        rollback_result = rollback_file(
            str(file_path)
        )

        assert rollback_result.success

        read_result = read_text_file(
            str(file_path)
        )

        assert (
            read_result.data["content"]
            == "Original"
        )


def test_read_nonexistent_file() -> None:
    result = read_text_file(
        "C:\\nonexistent_file_12345.txt"
    )

    assert not result.success
    assert result.code == "FILE_READ_FAILED"


def test_write_to_denied_directory() -> None:
    result = write_text_file(
        "C:\\Windows\\test_nova.txt",
        "test",
    )

    assert not result.success
    assert result.code == "FILE_WRITE_FAILED"
