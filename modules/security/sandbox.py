# modules/security/sandbox.py
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
import sys
from modules.domain.results import (
    ToolResult,
    VerificationResult,
)


logger = logging.getLogger("Sandbox")


SANDBOX_TIMEOUT = 30.0
SANDBOX_MAX_OUTPUT = 100_000
SANDBOX_WORKING_DIR = Path(
    "data/sandbox"
)


class PythonSandbox:
    """
    Изолированное выполнение Python-кода в отдельном процессе.

    Ограничения:
    - timeout;
    - максимальный размер вывода;
    - отдельная временная директория;
    - без доступа к .env;
    - без доступа к API-ключам;
    - без сетевого доступа (Windows Firewall rule — будущая версия).
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = SANDBOX_TIMEOUT,
        max_output_characters: int = SANDBOX_MAX_OUTPUT,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_output_characters = (
            max_output_characters
        )

    async def execute(
        self,
        code: str,
    ) -> ToolResult:
        if not code.strip():
            return ToolResult.failure(
                "EMPTY_CODE",
                "Код для выполнения пуст.",
            )

        SANDBOX_WORKING_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = int(time.time())
        sandbox_id = f"sandbox_{timestamp}_{os.getpid()}"

        sandbox_dir = (
            SANDBOX_WORKING_DIR / sandbox_id
        )
        sandbox_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        script_name = "script.py"
        script_path = sandbox_dir / script_name
        stdout_path = sandbox_dir / "stdout.txt"
        stderr_path = sandbox_dir / "stderr.txt"

        try:
            script_path.write_text(
                code,
                encoding="utf-8",
            )

            env = {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1",
            }

            # Не передаём .env переменные.
            for key in list(os.environ.keys()):
                if not key.startswith(
                    "NOVA_"
                ):
                    continue

                if key in {
                    "NOVA_LOCAL_STT_EXECUTABLE",
                    "NOVA_LOCAL_STT_MODEL",
                    "NOVA_LOCAL_LLM_EXECUTABLE",
                    "NOVA_LOCAL_LLM_MODEL",
                }:
                    env[key] = (
                        os.environ[key]
                    )

            process = await asyncio.create_subprocess_exec(
                sys.executable
                or "python",
                "-u",
                script_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(sandbox_dir),
                env=env,
            )


            try:
                stdout_bytes, stderr_bytes = (
                    await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.timeout_seconds,
                    )
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()

                return ToolResult.failure(
                    "SANDBOX_TIMEOUT",
                    (
                        "Выполнение кода превысило лимит "
                        f"{self.timeout_seconds:.0f} секунд."
                    ),
                    retryable=True,
                )

            stdout_text = stdout_bytes.decode(
                "utf-8",
                errors="replace",
            ).strip()

            stderr_text = stderr_bytes.decode(
                "utf-8",
                errors="replace",
            ).strip()

            stdout_path.write_text(
                stdout_text,
                encoding="utf-8",
            )
            stderr_path.write_text(
                stderr_text,
                encoding="utf-8",
            )

            output = stdout_text

            if stderr_text:
                output += (
                    f"\n[STDERR]\n{stderr_text}"
                )

            if len(output) > self.max_output_characters:
                output = (
                    output[
                        :self.max_output_characters
                    ]
                    + "\n...[вывод обрезан]..."
                )

            if process.returncode != 0:
                return ToolResult.failure(
                    "SANDBOX_NONZERO_EXIT",
                    (
                        f"Код завершился с кодом "
                        f"{process.returncode}."
                    ),
                    data={
                        "stdout": stdout_text,
                        "stderr": stderr_text,
                        "return_code": (
                            process.returncode
                        ),
                    },
                )

            return ToolResult.ok(
                "Код выполнен в sandbox.",
                data={
                    "output": output,
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "return_code": (
                        process.returncode
                    ),
                },
                verification=VerificationResult(
                    verified=True,
                    method="sandbox_execution",
                    confidence=1.0,
                    details=(
                        f"Код выполнен в изолированном "
                        f"процессе PID {process.pid}."
                    ),
                ),
            )

        except FileNotFoundError:
            return ToolResult.failure(
                "SANDBOX_PYTHON_NOT_FOUND",
                "Не удалось найти Python для sandbox.",
            )

        except OSError as exc:
            return ToolResult.failure(
                "SANDBOX_EXECUTION_FAILED",
                f"Ошибка sandbox: {exc}",
            )

        finally:
            # Очистка временных файлов.
            try:
                import shutil

                shutil.rmtree(
                    str(sandbox_dir),
                    ignore_errors=True,
                )
            except Exception:
                logger.exception(
                    "Не удалось очистить sandbox %s.",
                    sandbox_id,
                )
