# modules/agent/recovery.py
from __future__ import annotations

import asyncio
import logging
import os
import platform
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable

from modules.domain.results import ToolResult


logger = logging.getLogger("RecoveryEngine")


# MCP tools available for recovery operations
MCP_RECOVERY_TOOLS: set[str] = set()


def set_mcp_recovery_tools(tools: set[str]) -> None:
    """Set available MCP recovery tools."""
    global MCP_RECOVERY_TOOLS
    MCP_RECOVERY_TOOLS = tools.copy()


def get_mcp_recovery_tools() -> set[str]:
    """Get available MCP recovery tools."""
    return MCP_RECOVERY_TOOLS.copy()


class RecoveryAction(StrEnum):
    RETRY = "retry"
    FALLBACK = "fallback"
    ASK_USER = "ask_user"
    ROLLBACK = "rollback"
    ABORT = "abort"
    CONTINUE = "continue"


@dataclass(slots=True)
class RecoveryDecision:
    action: RecoveryAction
    reason: str

    delay_seconds: float = 0.0
    max_attempts: int = 1

    requires_user_input: bool = False
    should_rollback: bool = False


@dataclass(slots=True)
class RecoveryContext:
    operation_name: str
    attempt: int = 1
    max_attempts: int = 3

    has_fallback: bool = False
    has_rollback: bool = False

    user_denied: bool = False
    cancellation_requested: bool = False


class RecoveryEngine:
    """
    Выбирает стратегию восстановления после ошибки инструмента.

    Recovery Engine не повторяет действие самостоятельно без проверки:
    - идемпотентности;
    - лимита попыток;
    - типа ошибки;
    - решения пользователя;
    - наличия rollback.
    """

    NON_RETRYABLE_CODES = frozenset(
        {
            "POLICY_DENIED",
            "USER_DENIED",
            "TOOL_CANCELLED",
            "ARGUMENT_VALIDATION_FAILED",
            "INVALID_ARGUMENTS_JSON",
            "INVALID_ARGUMENTS_TYPE",
            "TOOL_NOT_FOUND",
            "INVALID_TOOL_CALL",
            "INVALID_TOOL_NAME",
            "APPLICATION_NOT_FOUND",
            "EMPTY_TEXT",
            "EMPTY_APPLICATION_NAME",
        }
    )

    USER_INPUT_CODES = frozenset(
        {
            "EMPTY_TEXT",
            "EMPTY_APPLICATION_NAME",
            "MISSING_REQUIRED_CONTEXT",
            "AMBIGUOUS_TARGET",
            "ACTIVE_WINDOW_CHANGED",
        }
    )

    FALLBACK_CODES = frozenset(
        {
            "UI_AUTOMATION_NOT_AVAILABLE",
            "ELEMENT_NOT_FOUND",
            "OCR_ENGINE_NOT_AVAILABLE",
            "PLAYWRIGHT_NOT_INSTALLED",
            "BROWSER_START_FAILED",
            "MODEL_ROUTE_FAILED",
        }
    )

    RETRYABLE_CODES = frozenset(
        {
            "TOOL_TIMEOUT",
            "PROCESS_START_FAILED",
            "BROWSER_NAVIGATION_FAILED",
            "BROWSER_TEXT_READ_FAILED",
            "BROWSER_CLICK_FAILED",
            "BROWSER_FILL_FAILED",
            "UI_AUTOMATION_ERROR",
            "CONNECTION_ERROR",
            "TEMPORARY_FAILURE",
        }
    )

    def decide(
        self,
        result: ToolResult,
        context: RecoveryContext,
    ) -> RecoveryDecision:
        if result.success:
            return RecoveryDecision(
                action=RecoveryAction.CONTINUE,
                reason="Операция завершена успешно.",
            )

        if context.cancellation_requested:
            return RecoveryDecision(
                action=RecoveryAction.ABORT,
                reason="Операция отменена пользователем.",
            )

        if context.user_denied:
            return RecoveryDecision(
                action=RecoveryAction.ABORT,
                reason=(
                    "Пользователь запретил выполнение. "
                    "Автоматический повтор запрещён."
                ),
            )

        if result.code in self.USER_INPUT_CODES:
            return RecoveryDecision(
                action=RecoveryAction.ASK_USER,
                reason=result.message,
                requires_user_input=True,
            )

        if result.code in self.NON_RETRYABLE_CODES:
            return RecoveryDecision(
                action=RecoveryAction.ABORT,
                reason=(
                    "Ошибка не допускает автоматический повтор: "
                    + result.message
                ),
            )

        if (
            result.code in self.FALLBACK_CODES
            and context.has_fallback
        ):
            return RecoveryDecision(
                action=RecoveryAction.FALLBACK,
                reason=(
                    "Основной способ не сработал, "
                    "доступен резервный механизм."
                ),
            )

        may_retry = (
            result.retryable
            or result.code in self.RETRYABLE_CODES
        )

        if (
            may_retry
            and context.attempt < context.max_attempts
        ):
            delay = min(
                2 ** max(0, context.attempt - 1),
                8,
            )

            return RecoveryDecision(
                action=RecoveryAction.RETRY,
                reason=(
                    f"Временная ошибка. Попытка "
                    f"{context.attempt + 1} из "
                    f"{context.max_attempts}."
                ),
                delay_seconds=float(delay),
                max_attempts=context.max_attempts,
            )

        if (
            context.has_rollback
            and result.rollback_token
        ):
            return RecoveryDecision(
                action=RecoveryAction.ROLLBACK,
                reason=(
                    "Операция завершилась ошибкой, "
                    "доступен откат."
                ),
                should_rollback=True,
            )

        return RecoveryDecision(
            action=RecoveryAction.ABORT,
            reason=(
                "Безопасная стратегия восстановления "
                "не найдена."
            ),
        )

    async def execute_with_recovery(
        self,
        operation: Callable[
            [int],
            Awaitable[ToolResult],
        ],
        *,
        operation_name: str,
        max_attempts: int = 3,
        has_fallback: bool = False,
        has_rollback: bool = False,
        cancellation_event: asyncio.Event | None = None,
    ) -> tuple[ToolResult, RecoveryDecision]:
        """
        Выполняет только безопасные автоматические повторы.

        Fallback, ASK_USER и ROLLBACK возвращаются вызывающему коду:
        конкретный механизм выбирает application layer.
        """
        last_result = ToolResult.failure(
            "OPERATION_NOT_STARTED",
            "Операция не была запущена.",
        )

        for attempt in range(1, max_attempts + 1):
            if (
                cancellation_event is not None
                and cancellation_event.is_set()
            ):
                cancelled_result = ToolResult.failure(
                    "TOOL_CANCELLED",
                    (
                        f"Операция '{operation_name}' "
                        "отменена."
                    ),
                )

                decision = RecoveryDecision(
                    action=RecoveryAction.ABORT,
                    reason="Операция отменена.",
                )

                return cancelled_result, decision

            try:
                last_result = await operation(attempt)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(
                    "Необработанная ошибка операции %s.",
                    operation_name,
                )

                last_result = ToolResult.failure(
                    "UNHANDLED_OPERATION_ERROR",
                    (
                        f"Необработанная ошибка "
                        f"'{operation_name}': {exc}"
                    ),
                    retryable=True,
                )

            context = RecoveryContext(
                operation_name=operation_name,
                attempt=attempt,
                max_attempts=max_attempts,
                has_fallback=has_fallback,
                has_rollback=has_rollback,
                cancellation_requested=(
                    cancellation_event is not None
                    and cancellation_event.is_set()
                ),
            )

            decision = self.decide(
                last_result,
                context,
            )

            logger.info(
                (
                    "Recovery decision: operation=%s "
                    "attempt=%s action=%s code=%s"
                ),
                operation_name,
                attempt,
                decision.action.value,
                last_result.code,
            )

            if decision.action == RecoveryAction.CONTINUE:
                return last_result, decision

            if decision.action != RecoveryAction.RETRY:
                return last_result, decision

            if decision.delay_seconds > 0:
                try:
                    if cancellation_event is None:
                        await asyncio.sleep(
                            decision.delay_seconds
                        )
                    else:
                        await asyncio.wait_for(
                            cancellation_event.wait(),
                            timeout=decision.delay_seconds,
                        )

                        cancelled_result = ToolResult.failure(
                            "TOOL_CANCELLED",
                            (
                                f"Операция '{operation_name}' "
                                "отменена во время ожидания."
                            ),
                        )

                        return (
                            cancelled_result,
                            RecoveryDecision(
                                action=RecoveryAction.ABORT,
                                reason="Операция отменена.",
                            ),
                        )

                except asyncio.TimeoutError:
                    pass

        final_decision = self.decide(
            last_result,
            RecoveryContext(
                operation_name=operation_name,
                attempt=max_attempts,
                max_attempts=max_attempts,
                has_fallback=has_fallback,
                has_rollback=has_rollback,
            ),
        )

        return last_result, final_decision


@dataclass(slots=True)
class DiagnosticResult:
    """Result of a self-diagnostic check."""
    component: str
    healthy: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class SelfDiagnostics:
    """
    Self-diagnostics for agent health monitoring.
    
    Checks system resources, configuration, and service availability.
    Used for graceful degradation when components fail.
    """
    
    def __init__(self) -> None:
        self._last_diagnostics: dict[str, DiagnosticResult] = {}
    
    async def run_diagnostics(self) -> dict[str, DiagnosticResult]:
        """Run all diagnostic checks and return results."""
        results = {
            "database": await self._check_database(),
            "storage": await self._check_storage(),
            "memory": await self._check_memory(),
            "filesystem": await self._check_filesystem(),
            "process_manager": await self._check_process_manager(),
            "model_gateway": await self._check_model_gateway(),
            "mcp_servers": await self._check_mcp_servers(),
        }
        self._last_diagnostics = results
        return results
    
    async def _check_database(self) -> DiagnosticResult:
        """Check database connectivity."""
        try:
            from modules.storage.database import Database
            db = Database()
            db.connection()  # Test connection
            return DiagnosticResult(
                component="database",
                healthy=True,
                message="Database connection OK",
            )
        except Exception as exc:
            return DiagnosticResult(
                component="database",
                healthy=False,
                message=f"Database connection failed: {exc}",
            )
    
    async def _check_storage(self) -> DiagnosticResult:
        """Check artifact storage availability."""
        try:
            from modules.storage.artifacts import ArtifactStore
            store = ArtifactStore()
            return DiagnosticResult(
                component="storage",
                healthy=True,
                message="Artifact storage OK",
            )
        except Exception as exc:
            return DiagnosticResult(
                component="storage",
                healthy=False,
                message=f"Storage check failed: {exc}",
            )
    
    async def _check_memory(self) -> DiagnosticResult:
        """Check memory system availability."""
        try:
            from modules.brain.memory import LocalMemory
            memory = LocalMemory()
            return DiagnosticResult(
                component="memory",
                healthy=True,
                message="Memory system OK",
            )
        except Exception as exc:
            return DiagnosticResult(
                component="memory",
                healthy=False,
                message=f"Memory check failed: {exc}",
            )
    
    async def _check_filesystem(self) -> DiagnosticResult:
        """Check filesystem permissions."""
        try:
            from pathlib import Path
            workspace = Path(os.getcwd())
            if not os.access(workspace, os.R_OK | os.W_OK):
                return DiagnosticResult(
                    component="filesystem",
                    healthy=False,
                    message="Workspace not accessible",
                )
            return DiagnosticResult(
                component="filesystem",
                healthy=True,
                message="Filesystem accessible",
                details={"workspace": str(workspace)},
            )
        except Exception as exc:
            return DiagnosticResult(
                component="filesystem",
                healthy=False,
                message=f"Filesystem check failed: {exc}",
            )
    
    async def _check_process_manager(self) -> DiagnosticResult:
        """Check process manager availability."""
        try:
            from modules.windows.process_manager import ProcessManager
            pm = ProcessManager()
            return DiagnosticResult(
                component="process_manager",
                healthy=True,
                message="Process manager OK",
            )
        except Exception as exc:
            return DiagnosticResult(
                component="process_manager",
                healthy=False,
                message=f"Process manager check failed: {exc}",
            )
    
    async def _check_model_gateway(self) -> DiagnosticResult:
        """Check model gateway availability."""
        try:
            from modules.brain.model_gateway import ModelGateway
            gateway = ModelGateway()
            return DiagnosticResult(
                component="model_gateway",
                healthy=True,
                message="Model gateway OK",
            )
        except Exception as exc:
            return DiagnosticResult(
                component="model_gateway",
                healthy=False,
                message=f"Model gateway check failed: {exc}",
            )
    
    async def _check_mcp_servers(self) -> DiagnosticResult:
        """Check MCP servers availability."""
        mcp_tools = get_mcp_recovery_tools()
        return DiagnosticResult(
            component="mcp_servers",
            healthy=len(mcp_tools) > 0,
            message=f"MCP tools available: {len(mcp_tools)}",
            details={"tools": list(mcp_tools)},
        )
    
    def get_degradation_mode(self) -> str:
        """
        Determine degradation mode based on diagnostic results.
        
        Returns:
            'full' - all systems healthy
            'degraded_network' - no network/external APIs
            'degraded_storage' - database/storage issues
            'degraded_full' - major components unavailable
        """
        if not self._last_diagnostics:
            return "full"
        
        issues = [
            r for r in self._last_diagnostics.values()
            if not r.healthy
        ]
        
        if len(issues) == 0:
            return "full"
        
        # Check for critical issues
        critical_components = {"database", "model_gateway"}
        failed_critical = [
            c for c in issues
            if c.component in critical_components
        ]
        
        if len(failed_critical) > 0:
            return "degraded_full"
        
        # Check for network-related issues
        network_components = {"mcp_servers", "storage"}
        failed_network = [
            c for c in issues
            if c.component in network_components
        ]
        
        if len(failed_network) > 0:
            return "degraded_network"
        
        return "degraded_storage"


class GracefulDegradation:
    """
    Graceful degradation manager.
    
    Adjusts agent behavior based on system health:
    - Reduces tool complexity when resources are limited
    - Falls back to simpler implementations
    - Provides degraded but functional responses
    """
    
    def __init__(self, diagnostics: SelfDiagnostics) -> None:
        self.diagnostics = diagnostics
        self._degradation_mode: str = "full"
    
    async def update_mode(self) -> str:
        """Update degradation mode based on latest diagnostics."""
        await self.diagnostics.run_diagnostics()
        self._degradation_mode = self.diagnostics.get_degradation_mode()
        return self._degradation_mode
    
    def get_alternative_tools(self) -> set[str]:
        """
        Get alternative tool set based on degradation mode.
        
        Returns simplified tool set when system is degraded.
        """
        if self._degradation_mode == "full":
            return set()  # No restrictions
        
        # In degraded mode, restrict to essential tools only
        essential_tools = {
            "get_current_time",
            "get_system_status",
            "type_text",
            "write_in_application",
            "search_in_memory",
        }
        
        # Add MCP recovery tools if available (they can help with recovery)
        mcp_tools = get_mcp_recovery_tools()
        
        return essential_tools | mcp_tools
    
    def should_use_mcp_fallback(self) -> bool:
        """Check if MCP fallback is appropriate."""
        return self._degradation_mode in {"degraded_network", "full"}
    
    def get_retry_delay_multiplier(self) -> float:
        """
        Get delay multiplier for retries in degraded mode.
        
        Increases delays when system is under stress.
        """
        if self._degradation_mode == "full":
            return 1.0
        elif self._degradation_mode == "degraded_network":
            return 2.0
        else:
            return 4.0
