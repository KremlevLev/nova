# modules/domain/results.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolResult:
    success: bool
    message: str
    code: str = "OK"
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    retryable: bool = False

    @classmethod
    def ok(
        cls,
        message: str,
        *,
        data: dict[str, Any] | None = None,
        artifacts: list[str] | None = None,
    ) -> "ToolResult":
        return cls(
            success=True,
            message=message,
            data=data or {},
            artifacts=artifacts or [],
        )

    @classmethod
    def failure(
        cls,
        code: str,
        message: str,
        *,
        data: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> "ToolResult":
        return cls(
            success=False,
            code=code,
            message=message,
            data=data or {},
            retryable=retryable,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "code": self.code,
            "message": self.message,
            "data": self.data,
            "artifacts": self.artifacts,
            "retryable": self.retryable,
        }

    def to_model_content(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
        )


@dataclass(slots=True)
class AssistantResponse:
    display_text: str
    speech_text: str
    success: bool = True
    error_code: str | None = None
