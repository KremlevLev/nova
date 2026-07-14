# scripts/build_installer.py
"""
Сборка Nova в единый исполняемый файл через PyInstaller.

Использование:
    python scripts/build_installer.py

Требования:
    py -m pip install pyinstaller
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_FILE = PROJECT_ROOT / "nova.spec"


def clean_build() -> None:
    for directory in [DIST_DIR, BUILD_DIR]:
        if directory.exists():
            shutil.rmtree(str(directory))

    if SPEC_FILE.exists():
        SPEC_FILE.unlink()


def build() -> None:
    print("=== Сборка Nova ===")

    clean_build()

    entry_point = str(
        PROJECT_ROOT / "main.py"
    )

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "Nova",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--add-data",
        f"core{os.pathsep}core",
        "--add-data",
        f"modules{os.pathsep}modules",
        "--add-data",
        f"data{os.pathsep}data",
        "--hidden-import",
        "openai",
        "--hidden-import",
        "sounddevice",
        "--hidden-import",
        "torch",
        "--hidden-import",
        "PIL",
        "--hidden-import",
        "pyautogui",
        "--hidden-import",
        "pyperclip",
        "--hidden-import",
        "keyboard",
        "--hidden-import",
        "psutil",
        "--hidden-import",
        "requests",
        "--hidden-import",
        "beautifulsoup4",
        "--hidden-import",
        "playwright",
        "--hidden-import",
        "PySide6",
        "--hidden-import",
        "winrt",
        "--collect-all",
        "openai",
        "--collect-all",
        "PySide6",
        "--collect-all",
        "playwright",
        entry_point,
    ]

    print("Запуск PyInstaller...")

    result = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
    )

    if result.returncode != 0:
        print(
            f"Ошибка сборки: {result.returncode}"
        )
        sys.exit(1)

    print(
        f"Сборка завершена. Исполняемый файл: "
        f"{DIST_DIR / 'Nova.exe'}"
    )


if __name__ == "__main__":
    build()
