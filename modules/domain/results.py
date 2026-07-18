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


@dataclass(slots=True)
class ToolObservation:
    """
    Сокращённый результат tool call для передачи модели.

    Полный результат сохраняется в ArtifactStore.
    Модели передаётся до 4000 символов с экстрактом.
    """
    tool_name: str
    success: bool
    code: str
    summary: str
    important_data: dict[str, Any] = field(
        default_factory=dict
    )
    excerpt: str = ""
    artifact_id: str | None = None
    retryable: bool = False
    omitted_characters: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "code": self.code,
            "summary": self.summary,
            "important_data": self.important_data,
            "excerpt": self.excerpt,
            "artifact_id": self.artifact_id,
            "retryable": self.retryable,
            "omitted_characters": self.omitted_characters,
        }

    @classmethod
    def from_tool_result(
        cls,
        tool_name: str,
        result: dict[str, Any],
        *,
        max_observation_chars: int = 4000,
    ) -> "ToolObservation":
        """
        Создаёт ToolObservation из ToolResult с ограничением длины.
        """
        summary = str(result.get("message") or "")[:200]

        # Извлекаем важные данные
        important: dict[str, Any] = {}
        for key in ("data", "error", "path", "url"):
            if key in result:
                important[key] = result[key]

        # Формируем excerpt
        full_content = json.dumps(
            result,
            ensure_ascii=False,
        )
        if len(full_content) > max_observation_chars:
            # Берём первые и последние релевантные части
            half = max_observation_chars // 2
            excerpt = (
                full_content[:half]
                + "\n...[truncated]...\n"
                + full_content[-half:]
            )
            omitted = len(full_content) - max_observation_chars
        else:
            excerpt = full_content
            omitted = 0

        return cls(
            tool_name=tool_name,
            success=bool(result.get("success")),
            code=str(result.get("code") or "OK"),
            summary=summary,
            important_data=important,
            excerpt=excerpt,
            artifact_id=result.get("artifact_id"),
            retryable=bool(result.get("retryable")),
            omitted_characters=omitted,
        )


@dataclass(slots=True)
class ExecutionCheckpoint:
    """
    Состояние выполнения задачи для передачи между провайдерами.

    Позволяет продолжить выполнение после fallback без повторения side effects.
    """
    task_id: str
    goal: str
    strategy: str
    completed_steps: list[str] = field(
        default_factory=list
    )
    pending_steps: list[str] = field(
        default_factory=list
    )
    failed_steps: list[str] = field(
        default_factory=list
    )
    observations: list[ToolObservation] = field(
        default_factory=list
    )
    artifact_ids: list[str] = field(
        default_factory=list
    )
    successful_signatures: set[str] = field(
        default_factory=set
    )
    rollback_tokens: list[str] = field(
        default_factory=list
    )
    remaining_budget: dict[str, int] = field(
        default_factory=lambda: {
            "model_calls": 2,
            "tool_calls": 10,
            "provider_attempts": 8,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "strategy": self.strategy,
            "completed_steps": self.completed_steps,
            "pending_steps": self.pending_steps,
            "failed_steps": self.failed_steps,
            "observations": [
                obs.to_dict()
                for obs in self.observations
            ],
            "artifact_ids": self.artifact_ids,
            "successful_signatures": list(
                self.successful_signatures
            ),
            "rollback_tokens": self.rollback_tokens,
            "remaining_budget": self.remaining_budget,
        }


@dataclass(slots=True)
class ExecutionLedger:
    """
    Журнал выполнения для идемпотентности tool calls.

    Отслеживает выполненные операции и позволяет избежать повторного выполнения.
    """
    task_id: str
    completed_signatures: set[str] = field(
        default_factory=set
    )
    operation_results: dict[str, ToolResult] = field(
        default_factory=dict
    )
    active_operations: set[str] = field(
        default_factory=set
    )
    rollback_tokens: list[str] = field(
        default_factory=list
    )

    def mark_completed(
        self,
        signature: str,
        result: ToolResult,
    ) -> None:
        """
        Помечает операцию как выполненную.
        """
        self.completed_signatures.add(signature)
        self.operation_results[signature] = result

        # Сохраняем rollback токен если есть
        if result.rollback_token:
            self.rollback_tokens.append(result.rollback_token)

    def is_completed(
        self,
        signature: str,
    ) -> bool:
        """
        Проверяет, была ли операция уже выполнена.
        """
        return signature in self.completed_signatures

    def get_result(
        self,
        signature: str,
    ) -> ToolResult | None:
        """
        Возвращает сохранённый результат операции.
        """
        return self.operation_results.get(signature)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "completed_signatures": list(
                self.completed_signatures
            ),
            "operation_results": {
                sig: res.to_dict() if hasattr(res, 'to_dict') else str(res)
                for sig, res in self.operation_results.items()
            },
            "active_operations": list(
                self.active_operations
            ),
            "rollback_tokens": self.rollback_tokens,
        }