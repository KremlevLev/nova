# modules/brain/model_router.py
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from core.config import (
    GROQ_API_KEYS,
    GROQ_CHAT_MODELS,
    GROQ_COMPLEX_MODELS,
    GROQ_TOOL_MODELS,
    GROQ_VISION_MODELS,
    OPENROUTER_API_KEYS,
    OPENROUTER_CHAT_MODELS,
    OPENROUTER_COMPLEX_MODELS,
    OPENROUTER_TOOL_MODELS,
    OPENROUTER_ULTRA_MODELS,
    OPENROUTER_VISION_MODELS,
)


class TaskComplexity(StrEnum):
    CHAT = "chat"
    BASIC_TOOL = "basic_tool"
    COMPLEX_TOOL = "complex_tool"
    ULTRA = "ultra"
    VISION = "vision"


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    provider: str
    model: str
    supports_tools: bool = True
    supports_vision: bool = False
    priority: int = 100

    @property
    def identity(self) -> str:
        return f"{self.provider}:{self.model}"


ULTRA_MARKERS = (
    "спроектируй архитектуру",
    "проведи полный аудит",
    "проанализируй весь проект",
    "найди причину во всем проекте",
    "мигрируй проект",
    "перепиши весь проект",
    "сложное исследование",
    "глубокий анализ",
    "сравни несколько подходов",
    "проанализируй репозиторий",
    "разработай стратегию",
    "проверь безопасность проекта",
)

COMPLEX_MARKERS = (
    "затем",
    "после чего",
    "а потом",
    "и потом",
    "а также",
    "сначала",
    "исправь",
    "установи",
    "создай проект",
    "запусти тесты",
    "проанализируй логи",
    "напиши код",
    "открой и напиши",
)

ACTION_VERBS = (
    "открой",
    "запусти",
    "закрой",
    "напиши",
    "вставь",
    "создай",
    "установи",
    "проверь",
    "найди",
    "скачай",
    "выполни",
    "нажми",
    "переключи",
    "сохрани",
    "удали",
    "перемести",
    "скопируй",
)


def classify_complexity(
    user_text: str,
    *,
    has_image: bool,
    needs_tools: bool,
) -> TaskComplexity:
    text = user_text.lower().strip()

    if has_image:
        return TaskComplexity.VISION

    if not needs_tools:
        return TaskComplexity.CHAT

    ultra_score = 0

    if len(text) > 1200:
        ultra_score += 2
    elif len(text) > 500:
        ultra_score += 1

    ultra_score += sum(
        2
        for marker in ULTRA_MARKERS
        if marker in text
    )

    code_markers = (
        "traceback",
        "архитектур",
        "безопасност",
        "рефактор",
        "docker",
        "kubernetes",
        "миграц",
        "база данных",
        "асинхрон",
    )
    ultra_score += sum(
        1
        for marker in code_markers
        if marker in text
    )

    if ultra_score >= 4:
        return TaskComplexity.ULTRA

    action_count = sum(
        1
        for verb in ACTION_VERBS
        if re.search(rf"\b{re.escape(verb)}\b", text)
    )

    if (
        action_count >= 2
        or any(marker in text for marker in COMPLEX_MARKERS)
        or len(text) > 300
    ):
        return TaskComplexity.COMPLEX_TOOL

    return TaskComplexity.BASIC_TOOL


def _candidates(
    provider: str,
    models: tuple[str, ...],
    *,
    supports_tools: bool,
    supports_vision: bool = False,
    start_priority: int,
) -> list[ModelCandidate]:
    return [
        ModelCandidate(
            provider=provider,
            model=model,
            supports_tools=supports_tools,
            supports_vision=supports_vision,
            priority=start_priority + index,
        )
        for index, model in enumerate(models)
    ]


def build_model_route(
    complexity: TaskComplexity,
) -> list[ModelCandidate]:
    candidates: list[ModelCandidate] = []

    if complexity == TaskComplexity.VISION:
        if GROQ_API_KEYS:
            candidates.extend(
                _candidates(
                    "groq",
                    GROQ_VISION_MODELS,
                    supports_tools=True,
                    supports_vision=True,
                    start_priority=10,
                )
            )

        if OPENROUTER_API_KEYS:
            candidates.extend(
                _candidates(
                    "openrouter",
                    OPENROUTER_VISION_MODELS,
                    supports_tools=True,
                    supports_vision=True,
                    start_priority=30,
                )
            )

    elif complexity == TaskComplexity.ULTRA:
        # Ультрасложные задачи сразу отправляем на OpenRouter.
        if OPENROUTER_API_KEYS:
            candidates.extend(
                _candidates(
                    "openrouter",
                    OPENROUTER_ULTRA_MODELS,
                    supports_tools=True,
                    start_priority=10,
                )
            )

        if GROQ_API_KEYS:
            candidates.extend(
                _candidates(
                    "groq",
                    GROQ_COMPLEX_MODELS,
                    supports_tools=True,
                    start_priority=40,
                )
            )

    elif complexity == TaskComplexity.COMPLEX_TOOL:
        if GROQ_API_KEYS:
            candidates.extend(
                _candidates(
                    "groq",
                    GROQ_COMPLEX_MODELS,
                    supports_tools=True,
                    start_priority=10,
                )
            )

        if OPENROUTER_API_KEYS:
            candidates.extend(
                _candidates(
                    "openrouter",
                    OPENROUTER_COMPLEX_MODELS,
                    supports_tools=True,
                    start_priority=30,
                )
            )

    elif complexity == TaskComplexity.BASIC_TOOL:
        if GROQ_API_KEYS:
            candidates.extend(
                _candidates(
                    "groq",
                    GROQ_TOOL_MODELS,
                    supports_tools=True,
                    start_priority=10,
                )
            )

        if OPENROUTER_API_KEYS:
            candidates.extend(
                _candidates(
                    "openrouter",
                    OPENROUTER_TOOL_MODELS,
                    supports_tools=True,
                    start_priority=30,
                )
            )

    else:
        if GROQ_API_KEYS:
            candidates.extend(
                _candidates(
                    "groq",
                    GROQ_CHAT_MODELS,
                    supports_tools=False,
                    start_priority=10,
                )
            )

        if OPENROUTER_API_KEYS:
            candidates.extend(
                _candidates(
                    "openrouter",
                    OPENROUTER_CHAT_MODELS,
                    supports_tools=False,
                    start_priority=30,
                )
            )

    unique: list[ModelCandidate] = []
    seen: set[str] = set()

    for candidate in sorted(
        candidates,
        key=lambda item: item.priority,
    ):
        if candidate.identity in seen:
            continue

        seen.add(candidate.identity)
        unique.append(candidate)

    return unique
