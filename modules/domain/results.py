# modules/domain/results.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class VerificationResult:
    """
    Результат независимой или встроенной проверки операции.

    verified:
        True  — результат подтверждён;
        False — проверка выполнена и не пройдена;
        None  — проверка не выполнялась.
    """

    verified: bool | None = None
    method: str = "not_performed"
    confidence: float = 0.0
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "method": self.method,
            "confidence": max(
                0.0,
                min(1.0, float(self.confidence)),
            ),
            "details": self.details,
        }


@dataclass(slots=True)
class ToolWarning:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
        }


@dataclass(slots=True)
class ToolResult:
    success: bool
    message: str
    code: str = "OK"

    data: dict[str, Any] = field(
        default_factory=dict
    )
    artifacts: list[str] = field(
        default_factory=list
    )
    warnings: list[ToolWarning] = field(
        default_factory=list
    )

    retryable: bool = False
    duration_ms: int | None = None
    rollback_token: str | None = None

    verification: VerificationResult = field(
        default_factory=VerificationResult
    )

    @classmethod
    def ok(
        cls,
        message: str,
        *,
        data: dict[str, Any] | None = None,
        artifacts: list[str] | None = None,
        warnings: list[ToolWarning] | None = None,
        duration_ms: int | None = None,
        rollback_token: str | None = None,
        verification: VerificationResult | None = None,
    ) -> "ToolResult":
        return cls(
            success=True,
            message=message,
            code="OK",
            data=data or {},
            artifacts=artifacts or [],
            warnings=warnings or [],
            duration_ms=duration_ms,
            rollback_token=rollback_token,
            verification=(
                verification
                if verification is not None
                else VerificationResult()
            ),
        )

    @classmethod
    def failure(
        cls,
        code: str,
        message: str,
        *,
        data: dict[str, Any] | None = None,
        artifacts: list[str] | None = None,
        warnings: list[ToolWarning] | None = None,
        retryable: bool = False,
        duration_ms: int | None = None,
        rollback_token: str | None = None,
        verification: VerificationResult | None = None,
    ) -> "ToolResult":
        return cls(
            success=False,
            message=message,
            code=code,
            data=data or {},
            artifacts=artifacts or [],
            warnings=warnings or [],
            retryable=retryable,
            duration_ms=duration_ms,
            rollback_token=rollback_token,
            verification=(
                verification
                if verification is not None
                else VerificationResult(
                    verified=False,
                    method="tool_failure",
                    confidence=1.0,
                    details=message,
                )
            ),
        )

    def add_warning(
        self,
        code: str,
        message: str,
    ) -> None:
        self.warnings.append(
            ToolWarning(
                code=code,
                message=message,
            )
        )

    def with_duration(
        self,
        duration_ms: int,
    ) -> "ToolResult":
        self.duration_ms = max(0, int(duration_ms))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "code": self.code,
            "message": self.message,
            "data": self.data,
            "artifacts": self.artifacts,
            "warnings": [
                warning.to_dict()
                for warning in self.warnings
            ],
            "retryable": self.retryable,
            "duration_ms": self.duration_ms,
            "rollback_token": self.rollback_token,
            "verification": (
                self.verification.to_dict()
            ),
        }

    def to_model_content(self) -> str:
        """
        Компактный JSON для возвращения модели.
        """
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

    data: dict[str, Any] = field(
        default_factory=dict
    )
