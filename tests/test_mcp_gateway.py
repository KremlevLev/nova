# tests/test_mcp_gateway.py
"""Tests for MCP Gateway and Recovery & Self-healing functionality."""
from __future__ import annotations

import asyncio

from modules.agent.recovery import (
    GracefulDegradation,
    RecoveryAction,
    RecoveryContext,
    RecoveryDecision,
    RecoveryEngine,
    DiagnosticResult,
    SelfDiagnostics,
    get_mcp_recovery_tools,
    set_mcp_recovery_tools,
)
from modules.domain.results import ToolResult


def test_mcp_recovery_tools_setter() -> None:
    """Test MCP recovery tools can be set and retrieved."""
    test_tools = {"mcp_recovery_rollback", "mcp_recovery_diagnose"}
    
    set_mcp_recovery_tools(test_tools)
    
    # Check via getter function (MCP_RECOVERY_TOOLS is module-level, not updated by import)
    assert get_mcp_recovery_tools() == test_tools


def test_mcp_recovery_tools_empty_by_default() -> None:
    """Test MCP recovery tools is empty by default."""
    set_mcp_recovery_tools(set())
    assert len(get_mcp_recovery_tools()) == 0


def test_recovery_engine_exists() -> None:
    """Test RecoveryEngine can be instantiated."""
    engine = RecoveryEngine()
    assert engine is not None


def test_recovery_decision_creation() -> None:
    """Test RecoveryDecision can be created."""
    decision = RecoveryDecision(
        action=RecoveryAction.ROLLBACK,
        reason="Test rollback",
        should_rollback=True,
    )
    
    assert decision.action == RecoveryAction.ROLLBACK
    assert decision.should_rollback is True
    assert decision.requires_user_input is False


def test_recovery_context_creation() -> None:
    """Test RecoveryContext can be created."""
    context = RecoveryContext(
        operation_name="test_op",
        has_fallback=True,
        has_rollback=True,
    )
    
    assert context.operation_name == "test_op"
    assert context.has_fallback is True
    assert context.has_rollback is True


def test_diagnostics_result_creation() -> None:
    """Test DiagnosticResult can be created."""
    result = DiagnosticResult(
        component="test_component",
        healthy=True,
        message="OK",
        details={"key": "value"},
    )
    
    assert result.component == "test_component"
    assert result.healthy is True
    assert result.details == {"key": "value"}


def test_self_diagnostics_initialization() -> None:
    """Test SelfDiagnostics can be initialized."""
    diagnostics = SelfDiagnostics()
    assert diagnostics is not None
    assert diagnostics.get_degradation_mode() == "full"


def test_graceful_degradation_initialization() -> None:
    """Test GracefulDegradation can be initialized."""
    diagnostics = SelfDiagnostics()
    degradation = GracefulDegradation(diagnostics)
    
    assert degradation.diagnostics == diagnostics
    assert degradation.get_retry_delay_multiplier() == 1.0


def test_graceful_degradation_full_mode() -> None:
    """Test GracefulDegradation in full mode has no restrictions."""
    diagnostics = SelfDiagnostics()
    degradation = GracefulDegradation(diagnostics)
    
    # In full mode, no tool restrictions
    alternative_tools = degradation.get_alternative_tools()
    assert len(alternative_tools) == 0


def test_graceful_degradation_degraded_mode_restricts_tools() -> None:
    """Test GracefulDegradation restricts tools in degraded mode."""
    diagnostics = SelfDiagnostics()
    degradation = GracefulDegradation(diagnostics)
    
    # Simulate degraded mode
    diagnostics._last_diagnostics = {
        "filesystem": DiagnosticResult(
            component="filesystem",
            healthy=False,
            message="Failed",
        ),
    }
    degradation._degradation_mode = "degraded_storage"
    
    alternative_tools = degradation.get_alternative_tools()
    
    assert "get_current_time" in alternative_tools
    assert "type_text" in alternative_tools


def test_graceful_degradation_mcp_fallback_check() -> None:
    """Test MCP fallback appropriateness check."""
    diagnostics = SelfDiagnostics()
    degradation = GracefulDegradation(diagnostics)
    
    # Full mode - can use MCP fallback
    degradation._degradation_mode = "full"
    assert degradation.should_use_mcp_fallback() is True
    
    # Degraded full - cannot use MCP fallback
    degradation._degradation_mode = "degraded_full"
    assert degradation.should_use_mcp_fallback() is False


def test_graceful_degradation_retry_delay_multiplier() -> None:
    """Test retry delay multiplier in degraded modes."""
    diagnostics = SelfDiagnostics()
    degradation = GracefulDegradation(diagnostics)
    
    # Full mode - normal delay
    degradation._degradation_mode = "full"
    assert degradation.get_retry_delay_multiplier() == 1.0
    
    # Network degraded - 2x delay
    degradation._degradation_mode = "degraded_network"
    assert degradation.get_retry_delay_multiplier() == 2.0
    
    # Full degraded - 4x delay
    degradation._degradation_mode = "degraded_full"
    assert degradation.get_retry_delay_multiplier() == 4.0


def test_degradation_mode_detection() -> None:
    """Test degradation mode detection logic."""
    diagnostics = SelfDiagnostics()
    
    # No issues - full mode
    diagnostics._last_diagnostics = {
        "database": DiagnosticResult(
            component="database",
            healthy=True,
            message="OK",
        ),
        "filesystem": DiagnosticResult(
            component="filesystem",
            healthy=True,
            message="OK",
        ),
    }
    assert diagnostics.get_degradation_mode() == "full"
    
    # Network issues - degraded_network
    diagnostics._last_diagnostics = {
        "database": DiagnosticResult(
            component="database",
            healthy=True,
            message="OK",
        ),
        "mcp_servers": DiagnosticResult(
            component="mcp_servers",
            healthy=False,
            message="Unavailable",
        ),
    }
    assert diagnostics.get_degradation_mode() == "degraded_network"
    
    # Critical failure - degraded_full
    diagnostics._last_diagnostics = {
        "database": DiagnosticResult(
            component="database",
            healthy=False,
            message="Failed",
        ),
    }
    assert diagnostics.get_degradation_mode() == "degraded_full"


def test_recovery_engine_decide_mcp_fallback() -> None:
    """Test RecoveryEngine decides fallback for MCP-related errors."""
    engine = RecoveryEngine()
    
    # Test that MCP tools are available for fallback
    set_mcp_recovery_tools({"mcp_recovery_rollback"})
    
    context = RecoveryContext(
        operation_name="test",
        has_fallback=True,
    )
    
    result = ToolResult.failure(
        "MODEL_ROUTE_FAILED",
        "Model routing failed",
    )
    
    decision = engine.decide(result, context)
    
    assert decision.action == RecoveryAction.FALLBACK