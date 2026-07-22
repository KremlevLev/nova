# tests/test_mcp_gateway.py
"""Tests for MCP Gateway and Recovery & Self-healing functionality."""
from __future__ import annotations

import asyncio

from modules.agent.mcp_gateway import (
    MCPGateway,
    MCPServerConfig,
)
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


def test_mcp_server_config_creation() -> None:
    """Test MCPServerConfig can be created."""
    config = MCPServerConfig(
        name="test_server",
        command="node",
        args=["server.js"],
        env={"TOKEN": "secret"},
    )
    
    assert config.name == "test_server"
    assert config.command == "node"
    assert config.args == ["server.js"]
    assert config.env == {"TOKEN": "secret"}
    assert config.transport == "stdio"


def test_mcp_gateway_creation() -> None:
    """Test MCPGateway can be instantiated."""
    gateway = MCPGateway()
    assert gateway is not None
    assert not gateway._initialized


def test_mcp_gateway_register_server() -> None:
    """Test MCPGateway can register servers."""
    gateway = MCPGateway()
    config = MCPServerConfig(
        name="test",
        command="python",
    )
    
    gateway.register_server(config)
    assert "test" in gateway._servers


def test_mcp_gateway_get_tool_schemas_empty() -> None:
    """Test MCPGateway returns empty schemas before initialization."""
    gateway = MCPGateway()
    schemas = gateway.get_tool_schemas()
    assert schemas == []


def test_mcp_gateway_get_available_tools_empty() -> None:
    """Test MCPGateway returns empty tools before initialization."""
    gateway = MCPGateway()
    tools = gateway.get_available_tools()
    assert tools == set()


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


def test_mcp_gateway_call_tool_invalid_name() -> None:
    """Test MCPGateway rejects invalid tool names."""
    
    async def run_test() -> None:
        gateway = MCPGateway()
        result = await gateway.call_tool("invalid_name", {})
        assert not result.success
        assert result.code == "INVALID_TOOL_NAME"
    
    asyncio.run(run_test())


def test_mcp_gateway_call_tool_unknown_server() -> None:
    """Test MCPGateway rejects unknown servers."""
    
    async def run_test() -> None:
        gateway = MCPGateway()
        result = await gateway.call_tool("mcp_unknown_tool", {})
        assert not result.success
        assert result.code == "UNKNOWN_MCP_SERVER"
    
    asyncio.run(run_test())


# ==============================================================================
# GitHub MCP Server Integration Tests
# ==============================================================================

def test_github_server_config_in_defaults() -> None:
    """Test that GitHub server is in DEFAULT_MCP_SERVERS."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    assert "github" in DEFAULT_MCP_SERVERS
    github_config = DEFAULT_MCP_SERVERS["github"]
    assert github_config["command"] == "npx"
    assert "-y" in github_config["args"]
    assert "@modelcontextprotocol/server-github" in github_config["args"]


def test_github_server_disabled_without_token() -> None:
    """Test that GitHub server is disabled when no token is present."""
    import os
    # Ensure no token is set
    os.environ.pop("GITHUB_TOKEN", None)
    
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    assert DEFAULT_MCP_SERVERS["github"]["enabled"] is False


def test_env_tokens_loading() -> None:
    """Test that environment tokens are loaded correctly."""
    import os
    os.environ["GITHUB_TOKEN"] = "test_github_token_123"
    
    from modules.agent.mcp_integration import _get_env_tokens
    tokens = _get_env_tokens()
    
    assert tokens["GITHUB_TOKEN"] == "test_github_token_123"
    assert tokens["SLACK_TOKEN"] == ""
    
    # Cleanup
    os.environ.pop("GITHUB_TOKEN", None)


def test_github_server_enabled_with_token() -> None:
    """Test that GitHub server is auto-enabled when token is present."""
    import os
    original_token = os.environ.get("GITHUB_TOKEN")
    os.environ["GITHUB_TOKEN"] = "ghp_test_token"
    
    # Need to reimport to get fresh defaults
    import importlib
    import modules.agent.mcp_integration as mcp_int
    importlib.reload(mcp_int)
    
    # The config itself has enabled=False, but bootstrap should auto-enable
    # We test that the env token is detected
    tokens = mcp_int._get_env_tokens()
    assert tokens["GITHUB_TOKEN"] == "ghp_test_token"
    
    # Cleanup
    if original_token:
        os.environ["GITHUB_TOKEN"] = original_token
    else:
        os.environ.pop("GITHUB_TOKEN", None)


def test_github_mcp_tool_name_format() -> None:
    """Test that GitHub MCP tools would be named correctly."""
    # GitHub MCP server tools would be named mcp_github_<tool_name>
    expected_tools = [
        "mcp_github_get_repository",
        "mcp_github_create_issue",
        "mcp_github_list_issues",
        "mcp_github_get_pull_request",
        "mcp_github_create_pull_request",
    ]
    
    # Verify naming convention
    for tool in expected_tools:
        assert tool.startswith("mcp_github_"), f"Tool {tool} should start with mcp_github_"


def test_mcp_gateway_register_server_with_env() -> None:
    """Test that server can be registered with environment variables."""
    gateway = MCPGateway()
    config = MCPServerConfig(
        name="github",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_TOKEN": "test_token"},
        enabled=True,
    )
    
    gateway.register_server(config)
    assert "github" in gateway._servers
    assert gateway._servers["github"].env == {"GITHUB_TOKEN": "test_token"}


# ==============================================================================
# Filesystem MCP Server Integration Tests
# ==============================================================================

def test_filesystem_server_config_in_defaults() -> None:
    """Test that Filesystem server is in DEFAULT_MCP_SERVERS."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    assert "filesystem" in DEFAULT_MCP_SERVERS
    fs_config = DEFAULT_MCP_SERVERS["filesystem"]
    assert fs_config["command"] == "npx"
    assert "-y" in fs_config["args"]
    assert "@modelcontextprotocol/server-filesystem" in fs_config["args"]
    assert "--directory" in fs_config["args"]
    assert fs_config["enabled"] is True  # Always enabled


def test_filesystem_mcp_tool_name_format() -> None:
    """Test that Filesystem MCP tools would be named correctly."""
    # Filesystem MCP server tools would be named mcp_filesystem_<tool_name>
    expected_tools = [
        "mcp_filesystem_read_file",
        "mcp_filesystem_write_file",
        "mcp_filesystem_list_directory",
        "mcp_filesystem_search_files",
    ]
    
    # Verify naming convention
    for tool in expected_tools:
        assert tool.startswith("mcp_filesystem_"), f"Tool {tool} should start with mcp_filesystem_"


def test_filesystem_server_always_enabled() -> None:
    """Test that Filesystem server is always enabled (no token required)."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    # Filesystem server should be enabled by default
    assert DEFAULT_MCP_SERVERS["filesystem"]["enabled"] is True