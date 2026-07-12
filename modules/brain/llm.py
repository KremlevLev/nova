# modules/brain/llm.py
from __future__ import annotations

import logging
from typing import Any

from modules.brain.model_gateway import (
    ModelGateway,
    ModelResponse,
)
from modules.brain.model_router import ModelCandidate
from modules.brain.tool_calls import extract_xml_tool_calls


logger = logging.getLogger("NovaLLM")


class NovaLLM:
    def __init__(self, model: str | None = None) -> None:
        self.primary_model = model
        self.history: list[dict[str, Any]] = []
        self.gateway = ModelGateway()

    async def complete(
        self,
        *,
        candidates,
        messages,
        tools=None,
        allow_tools=True,
        requires_vision=False,
    ):
        return await self.gateway.complete(
            candidates=candidates,
            messages=messages,
            tools=tools,
            allow_tools=allow_tools,
            requires_vision=requires_vision,
        )

    async def close(self) -> None:
        await self.gateway.close()

    def reset_context(self) -> None:
        self.history.clear()

    def provider_health(self) -> dict[str, Any]:
        return self.gateway.health_snapshot()


__all__ = [
    "NovaLLM",
    "ModelResponse",
    "extract_xml_tool_calls",
]
