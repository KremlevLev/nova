# scripts/install_dependencies.py
"""
Проверка и установка зависимостей Nova.

Использование:
    python scripts/install_dependencies.py
"""

import subprocess
import sys


REQUIREMENTS = [
    "openai",
    "python-dotenv",
    "requests",
    "beautifulsoup4",
    "sounddevice",
    "numpy",
    "psutil",
    "pyautogui",
    "pyperclip",
    "keyboard",
    "pillow",
    "playwright",
    "PySide6",
]

OPTIONAL_REQUIREMENTS = {
    "torch": (
        "torch",
        [
            "--index-url",
            "https://download.pytorch.org/whl/cpu",
        ],
    ),
    "winrt": ("winrt", []),
    "uiautomation": ("uiautomation", []),
}


def install(
    package: str,
    *,
    extra_args: list[str] | None = None,
) -> bool:
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        package,
    ]

    if extra_args:
        command.extend(extra_args)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(
            f"  Ошибка установки {package}: "
            f"{result.stderr.strip()}"
        )
        return False

    print(f"  {package} установлен.")
    return True


def main() -> None:
    print("=== Установка зависимостей Nova ===\n")

    print("Основные зависимости:")
    for package in REQUIREMENTS:
        install(package)

    print("\nОпциональные зависимости:")
    for name, (
        package,
        extra_args,
    ) in OPTIONAL_REQUIREMENTS.items():
        print(f"  {name} ({package})...")
        install(
            package,
            extra_args=extra_args,
        )

    print("\nУстановка Playwright Chromium...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "playwright",
            "install",
            "chromium",
        ],
    )

    print("\n=== Установка завершена ===")


if __name__ == "__main__":
    main()
