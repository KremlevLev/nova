# modules/local/inference.py
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


logger = logging.getLogger("LocalInference")


@dataclass(slots=True)
class LocalSTTConfig:
    executable: Path
    model_path: Path

    language: str = "ru"
    timeout_seconds: float = 120.0

    @property
    def is_configured(self) -> bool:
        return (
            self.executable.is_file()
            and self.model_path.is_file()
        )

    @classmethod
    def from_environment(
        cls,
    ) -> "LocalSTTConfig":
        executable = Path(
            os.getenv(
                "NOVA_LOCAL_STT_EXECUTABLE",
                "",
            )
        )

        model_path = Path(
            os.getenv(
                "NOVA_LOCAL_STT_MODEL",
                "",
            )
        )

        return cls(
            executable=executable,
            model_path=model_path,
            language=os.getenv(
                "NOVA_LOCAL_STT_LANGUAGE",
                "ru",
            ),
            timeout_seconds=float(
                os.getenv(
                    "NOVA_LOCAL_STT_TIMEOUT",
                    "120",
                )
            ),
        )


@dataclass(slots=True)
class LocalLLMConfig:
    executable: Path
    model_path: Path

    context_size: int = 4096
    max_output_tokens: int = 384
    temperature: float = 0.2
    timeout_seconds: float = 180.0
    threads: int = 4

    @property
    def is_configured(self) -> bool:
        return (
            self.executable.is_file()
            and self.model_path.is_file()
        )

    @classmethod
    def from_environment(
        cls,
    ) -> "LocalLLMConfig":
        return cls(
            executable=Path(
                os.getenv(
                    "NOVA_LOCAL_LLM_EXECUTABLE",
                    "",
                )
            ),
            model_path=Path(
                os.getenv(
                    "NOVA_LOCAL_LLM_MODEL",
                    "",
                )
            ),
            context_size=int(
                os.getenv(
                    "NOVA_LOCAL_LLM_CONTEXT",
                    "4096",
                )
            ),
            max_output_tokens=int(
                os.getenv(
                    "NOVA_LOCAL_LLM_MAX_TOKENS",
                    "384",
                )
            ),
            temperature=float(
                os.getenv(
                    "NOVA_LOCAL_LLM_TEMPERATURE",
                    "0.2",
                )
            ),
            timeout_seconds=float(
                os.getenv(
                    "NOVA_LOCAL_LLM_TIMEOUT",
                    "180",
                )
            ),
            threads=int(
                os.getenv(
                    "NOVA_LOCAL_LLM_THREADS",
                    "4",
                )
            ),
        )


@dataclass(slots=True)
class LocalInferenceResult:
    success: bool
    text: str = ""
    error: str = ""
    return_code: int | None = None

    stdout: str = ""
    stderr: str = ""


class LocalSTTFallback:
    """
    Локальный STT через whisper.cpp.

    Рекомендуется для вашего ноутбука:
    - ggml-tiny.bin: минимальная нагрузка;
    - ggml-base.bin: лучше качество, всё ещё приемлемо;
    - без GPU offload.
    """

    def __init__(
        self,
        config: LocalSTTConfig | None = None,
    ) -> None:
        self.config = (
            config
            or LocalSTTConfig.from_environment()
        )

        self._lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return self.config.is_configured

    async def transcribe(
        self,
        wav_path: str | Path,
    ) -> LocalInferenceResult:
        if not self.available:
            return LocalInferenceResult(
                success=False,
                error=(
                    "Локальный STT не настроен. "
                    "Укажите NOVA_LOCAL_STT_EXECUTABLE "
                    "и NOVA_LOCAL_STT_MODEL."
                ),
            )

        resolved_audio = Path(wav_path).resolve()

        if not resolved_audio.is_file():
            return LocalInferenceResult(
                success=False,
                error=(
                    f"Аудиофайл не найден: "
                    f"{resolved_audio}"
                ),
            )

        async with self._lock:
            output_prefix = Path(
                tempfile.gettempdir()
            ) / (
                f"nova_whisper_"
                f"{os.getpid()}_"
                f"{id(asyncio.current_task())}"
            )

            output_file = Path(
                str(output_prefix) + ".txt"
            )

            command = [
                str(self.config.executable),
                "-m",
                str(self.config.model_path),
                "-f",
                str(resolved_audio),
                "-l",
                self.config.language,
                "-nt",
                "-otxt",
                "-of",
                str(output_prefix),
            ]

            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout_bytes, stderr_bytes = (
                        await asyncio.wait_for(
                            process.communicate(),
                            timeout=(
                                self.config.timeout_seconds
                            ),
                        )
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.communicate()

                    return LocalInferenceResult(
                        success=False,
                        error=(
                            "Локальный STT превысил "
                            "лимит времени."
                        ),
                    )

                stdout = stdout_bytes.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

                stderr = stderr_bytes.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

                if process.returncode != 0:
                    return LocalInferenceResult(
                        success=False,
                        error=(
                            "whisper.cpp завершился "
                            f"с кодом {process.returncode}."
                        ),
                        return_code=process.returncode,
                        stdout=stdout,
                        stderr=stderr,
                    )

                if output_file.exists():
                    text = output_file.read_text(
                        encoding="utf-8",
                        errors="replace",
                    ).strip()
                else:
                    text = stdout.strip()

                if not text:
                    return LocalInferenceResult(
                        success=False,
                        error=(
                            "Локальный STT вернул "
                            "пустую транскрипцию."
                        ),
                        return_code=process.returncode,
                        stdout=stdout,
                        stderr=stderr,
                    )

                return LocalInferenceResult(
                    success=True,
                    text=text,
                    return_code=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                )

            except FileNotFoundError:
                return LocalInferenceResult(
                    success=False,
                    error=(
                        "Не найден whisper.cpp executable: "
                        f"{self.config.executable}"
                    ),
                )

            except OSError as exc:
                return LocalInferenceResult(
                    success=False,
                    error=(
                        "Не удалось запустить локальный "
                        f"STT: {exc}"
                    ),
                )

            finally:
                try:
                    output_file.unlink(
                        missing_ok=True
                    )
                except OSError:
                    pass


class LocalLLMFallback:
    """
    Локальный текстовый fallback через llama.cpp.

    Не используется для tool calling. Его назначение:
    - обычный чат;
    - короткие объяснения;
    - аварийный ответ при недоступности облака.

    Для 16 ГБ RAM:
    - 1–1.5B Q4_K_M — оптимально;
    - 3B Q4_K_M — допустимо;
    - 7B и выше не рекомендуется для фоновой Nova.
    """

    def __init__(
        self,
        config: LocalLLMConfig | None = None,
    ) -> None:
        self.config = (
            config
            or LocalLLMConfig.from_environment()
        )

        self._lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return self.config.is_configured

    async def generate(
        self,
        prompt: str,
    ) -> LocalInferenceResult:
        if not self.available:
            return LocalInferenceResult(
                success=False,
                error=(
                    "Локальный LLM не настроен. "
                    "Укажите NOVA_LOCAL_LLM_EXECUTABLE "
                    "и NOVA_LOCAL_LLM_MODEL."
                ),
            )

        clean_prompt = prompt.strip()

        if not clean_prompt:
            return LocalInferenceResult(
                success=False,
                error="Промпт локальной модели пуст.",
            )

        # Защита от чрезмерного CLI-аргумента.
        clean_prompt = clean_prompt[-16_000:]

        command = [
            str(self.config.executable),
            "-m",
            str(self.config.model_path),
            "-p",
            clean_prompt,
            "-n",
            str(self.config.max_output_tokens),
            "-c",
            str(self.config.context_size),
            "-t",
            str(self.config.threads),
            "--temp",
            str(self.config.temperature),
            "--no-display-prompt",
        ]

        async with self._lock:
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout_bytes, stderr_bytes = (
                        await asyncio.wait_for(
                            process.communicate(),
                            timeout=(
                                self.config.timeout_seconds
                            ),
                        )
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.communicate()

                    return LocalInferenceResult(
                        success=False,
                        error=(
                            "Локальный LLM превысил "
                            "лимит времени."
                        ),
                    )

                stdout = stdout_bytes.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

                stderr = stderr_bytes.decode(
                    "utf-8",
                    errors="replace",
                ).strip()

                if process.returncode != 0:
                    return LocalInferenceResult(
                        success=False,
                        error=(
                            "llama.cpp завершился "
                            f"с кодом {process.returncode}."
                        ),
                        return_code=process.returncode,
                        stdout=stdout,
                        stderr=stderr,
                    )

                if not stdout:
                    return LocalInferenceResult(
                        success=False,
                        error=(
                            "Локальный LLM вернул "
                            "пустой ответ."
                        ),
                        return_code=process.returncode,
                        stderr=stderr,
                    )

                return LocalInferenceResult(
                    success=True,
                    text=stdout,
                    return_code=process.returncode,
                    stdout=stdout,
                    stderr=stderr,
                )

            except FileNotFoundError:
                return LocalInferenceResult(
                    success=False,
                    error=(
                        "Не найден llama.cpp executable: "
                        f"{self.config.executable}"
                    ),
                )

            except OSError as exc:
                return LocalInferenceResult(
                    success=False,
                    error=(
                        "Не удалось запустить локальный "
                        f"LLM: {exc}"
                    ),
                )


def messages_to_local_prompt(
    messages: list[dict[str, Any]],
) -> str:
    """
    Преобразует OpenAI messages в компактный промпт.

    Изображения, tool calls и большие бинарные данные
    локальному fallback не передаются.
    """
    lines: list[str] = []

    role_names = {
        "system": "Система",
        "user": "Пользователь",
        "assistant": "Ассистент",
        "tool": "Инструмент",
    }

    for message in messages[-12:]:
        role = str(
            message.get("role", "user")
        )
        content = message.get("content", "")

        if isinstance(content, list):
            text_parts: list[str] = []

            for item in content:
                if not isinstance(item, dict):
                    continue

                if item.get("type") == "text":
                    text_parts.append(
                        str(item.get("text") or "")
                    )

            content_text = "\n".join(
                text_parts
            )
        else:
            content_text = str(content or "")

        if not content_text.strip():
            continue

        # Большие tool outputs не отправляем целиком.
        content_text = content_text[:4_000]

        lines.append(
            (
                f"{role_names.get(role, role)}: "
                f"{content_text}"
            )
        )

    lines.append("Ассистент:")

    return "\n\n".join(lines)
