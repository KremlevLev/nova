# tests/test_local_inference.py
from __future__ import annotations

from pathlib import Path

from modules.local.inference import (
    LocalLLMConfig,
    LocalLLMFallback,
    LocalSTTConfig,
    LocalSTTFallback,
    messages_to_local_prompt,
)


def test_local_stt_unavailable_without_files() -> None:
    fallback = LocalSTTFallback(
        LocalSTTConfig(
            executable=Path(
                "missing-whisper.exe"
            ),
            model_path=Path(
                "missing-model.bin"
            ),
        )
    )

    assert not fallback.available


def test_local_llm_unavailable_without_files() -> None:
    fallback = LocalLLMFallback(
        LocalLLMConfig(
            executable=Path(
                "missing-llama.exe"
            ),
            model_path=Path(
                "missing-model.gguf"
            ),
        )
    )

    assert not fallback.available


def test_messages_to_local_prompt() -> None:
    prompt = messages_to_local_prompt(
        [
            {
                "role": "system",
                "content": "Отвечай кратко.",
            },
            {
                "role": "user",
                "content": "Привет.",
            },
        ]
    )

    assert "Система: Отвечай кратко." in prompt
    assert "Пользователь: Привет." in prompt
    assert prompt.endswith("Ассистент:")


def test_images_are_not_embedded_in_local_prompt() -> None:
    prompt = messages_to_local_prompt(
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Что на экране?",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,secret"
                        },
                    },
                ],
            }
        ]
    )

    assert "Что на экране?" in prompt
    assert "base64" not in prompt
    assert "secret" not in prompt
