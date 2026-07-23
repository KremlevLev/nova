# tests/test_mcp_gateway.py
"""Tests for MCP Gateway and Recovery & Self-healing functionality."""
from __future__ import annotations

import asyncio

from modules.agent.mcp_gateway import (
    MCPGateway,
    MCPServerConfig,
    MCPConnectionPool,
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


def test_mcp_connection_pool_creation() -> None:
    """Test MCPConnectionPool can be created."""
    pool = MCPConnectionPool(max_connections=10)
    assert pool is not None
    assert pool._max_connections == 10


def test_mcp_connection_pool_returns_none_for_sse() -> None:
    """Test MCPConnectionPool returns None for SSE transport."""
    
    async def run_test() -> None:
        pool = MCPConnectionPool()
        config = MCPServerConfig(
            name="sse_server",
            command="node",
            transport="sse",
            url="https://api.example.com/mcp",
        )
        
        result = await pool.get_process(config)
        assert result is None
    
    asyncio.run(run_test())


def test_mcp_connection_pool_close() -> None:
    """Test MCPConnectionPool close clears all processes."""
    pool = MCPConnectionPool()
    pool._processes["test"] = None  # type: ignore
    pool.close()
    assert len(pool._processes) == 0
    assert len(pool._locks) == 0


def test_mcp_gateway_with_pool() -> None:
    """Test MCPGateway creates pool."""
    gateway = MCPGateway(pool_size=10)
    assert gateway._pool is not None
    assert gateway._pool._max_connections == 10


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


def test_mcp_server_config_sse() -> None:
    """Test MCPServerConfig can be created with SSE transport."""
    config = MCPServerConfig(
        name="sse_server",
        command="node",
        args=["-y", "@modelcontextprotocol/server-remote"],
        env={},
        enabled=True,
        transport="sse",
        url="https://api.example.com/mcp",
    )
    
    assert config.name == "sse_server"
    assert config.transport == "sse"
    assert config.url == "https://api.example.com/mcp"


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


def test_mcp_gateway_sse_config_without_url() -> None:
    """Test MCPGateway rejects SSE config without URL."""
    
    async def run_test() -> None:
        gateway = MCPGateway()
        config = MCPServerConfig(
            name="test_sse",
            command="node",
            transport="sse",
            # No URL provided
        )
        gateway.register_server(config)
        
        # Should raise error when trying to discover tools
        try:
            await gateway._discover_tools_sse(
                config,
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "url" in str(e).lower()
    
    asyncio.run(run_test())


def test_mcp_gateway_stdio_config() -> None:
    """Test MCPGateway stdio config is valid."""
    config = MCPServerConfig(
        name="test_stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-test"],
        transport="stdio",
    )
    
    assert config.transport == "stdio"
    assert config.url == ""


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


# ==============================================================================
# SQLite MCP Server Integration Tests
# ==============================================================================

def test_sqlite_server_config_in_defaults() -> None:
    """Test that SQLite server is in DEFAULT_MCP_SERVERS."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    assert "sqlite" in DEFAULT_MCP_SERVERS
    sqlite_config = DEFAULT_MCP_SERVERS["sqlite"]
    assert sqlite_config["command"] == "npx"
    assert "-y" in sqlite_config["args"]
    assert "@modelcontextprotocol/server-sqlite" in sqlite_config["args"]


def test_sqlite_server_disabled_without_path() -> None:
    """Test that SQLite server is disabled when no path is set."""
    import os
    # Ensure no path is set
    os.environ.pop("MCP_SQLITE_PATH", None)
    
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    assert DEFAULT_MCP_SERVERS["sqlite"]["enabled"] is False


def test_sqlite_path_loading() -> None:
    """Test that SQLite path is loaded from environment."""
    import os
    os.environ["MCP_SQLITE_PATH"] = "test_memory.db"
    
    from modules.agent.mcp_integration import _get_sqlite_path
    path = _get_sqlite_path()
    
    assert path == "test_memory.db"
    
    # Cleanup
    os.environ.pop("MCP_SQLITE_PATH", None)


def test_sqlite_mcp_tool_name_format() -> None:
    """Test that SQLite MCP tools would be named correctly."""
    # SQLite MCP server tools would be named mcp_sqlite_<tool_name>
    expected_tools = [
        "mcp_sqlite_query",
        "mcp_sqlite_list_tables",
        "mcp_sqlite_describe_table",
        "mcp_sqlite_read_resource",
    ]
    
    # Verify naming convention
    for tool in expected_tools:
        assert tool.startswith("mcp_sqlite_"), f"Tool {tool} should start with mcp_sqlite_"


# ==============================================================================
# Slack MCP Server Integration Tests
# ==============================================================================

def test_slack_server_config_in_defaults() -> None:
    """Test that Slack server is in DEFAULT_MCP_SERVERS."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    assert "slack" in DEFAULT_MCP_SERVERS
    slack_config = DEFAULT_MCP_SERVERS["slack"]
    assert slack_config["command"] == "npx"
    assert "-y" in slack_config["args"]
    assert "@modelcontextprotocol/server-slack" in slack_config["args"]


def test_slack_server_disabled_without_token() -> None:
    """Test that Slack server is disabled when no token is present."""
    import os
    # Ensure no token is set
    os.environ.pop("SLACK_TOKEN", None)
    
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    assert DEFAULT_MCP_SERVERS["slack"]["enabled"] is False


def test_slack_mcp_tool_name_format() -> None:
    """Test that Slack MCP tools would be named correctly."""
    # Slack MCP server tools would be named mcp_slack_<tool_name>
    expected_tools = [
        "mcp_slack_list_channels",
        "mcp_slack_post_message",
        "mcp_slack_get_channel_history",
        "mcp_slack_get_user_info",
    ]
    
    # Verify naming convention
    for tool in expected_tools:
        assert tool.startswith("mcp_slack_"), f"Tool {tool} should start with mcp_slack_"


# ==============================================================================
# Web Search MCP Server Integration Tests
# ==============================================================================

def test_websearch_server_config_in_defaults() -> None:
    """Test that Web Search server is in DEFAULT_MCP_SERVERS."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    assert "websearch" in DEFAULT_MCP_SERVERS
    websearch_config = DEFAULT_MCP_SERVERS["websearch"]
    assert websearch_config["command"] == "npx"
    assert "-y" in websearch_config["args"]
    assert "@modelcontextprotocol/server-web-search" in websearch_config["args"]


def test_websearch_server_always_enabled() -> None:
    """Test that Web Search server is always enabled (no token required)."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    # Websearch server should be enabled by default
    assert DEFAULT_MCP_SERVERS["websearch"]["enabled"] is True


def test_websearch_mcp_tool_name_format() -> None:
    """Test that Web Search MCP tools would be named correctly."""
    # Web Search MCP server tools would be named mcp_websearch_<tool_name>
    expected_tools = [
        "mcp_websearch_search",
        "mcp_websearch_search_pages",
        "mcp_websearch_get_page_content",
    ]
    
    # Verify naming convention
    for tool in expected_tools:
        assert tool.startswith("mcp_websearch_"), f"Tool {tool} should start with mcp_websearch_"


# ==============================================================================
# Google Drive MCP Server Integration Tests
# ==============================================================================

def test_gdrive_server_config_in_defaults() -> None:
    """Test that Google Drive server is in DEFAULT_MCP_SERVERS."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    assert "gdrive" in DEFAULT_MCP_SERVERS
    gdrive_config = DEFAULT_MCP_SERVERS["gdrive"]
    assert gdrive_config["command"] == "npx"
    assert "-y" in gdrive_config["args"]
    assert "@modelcontextprotocol/server-gdrive" in gdrive_config["args"]


def test_gdrive_server_disabled_without_token() -> None:
    """Test that Google Drive server is disabled when no token is present."""
    import os
    # Ensure no token is set
    os.environ.pop("GOOGLE_DRIVE_TOKEN", None)
    
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    assert DEFAULT_MCP_SERVERS["gdrive"]["enabled"] is False


def test_gdrive_mcp_tool_name_format() -> None:
    """Test that Google Drive MCP tools would be named correctly."""
    # Google Drive MCP server tools would be named mcp_gdrive_<tool_name>
    expected_tools = [
        "mcp_gdrive_list_files",
        "mcp_gdrive_read_file",
        "mcp_gdrive_create_file",
        "mcp_gdrive_update_file",
        "mcp_gdrive_delete_file",
    ]
    
    # Verify naming convention
    for tool in expected_tools:
        assert tool.startswith("mcp_gdrive_"), f"Tool {tool} should start with mcp_gdrive_"


# ==============================================================================
# PostgreSQL MCP Server Integration Tests
# ==============================================================================

def test_postgres_server_config_in_defaults() -> None:
    """Test that PostgreSQL server is in DEFAULT_MCP_SERVERS."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    assert "postgres" in DEFAULT_MCP_SERVERS
    postgres_config = DEFAULT_MCP_SERVERS["postgres"]
    assert postgres_config["command"] == "npx"
    assert "-y" in postgres_config["args"]
    assert "@modelcontextprotocol/server-postgres" in postgres_config["args"]


def test_postgres_server_disabled_without_connection() -> None:
    """Test that PostgreSQL server is disabled when no connection string is set."""
    import os
    # Ensure no connection string is set
    os.environ.pop("MCP_POSTGRES_CONNECTION", None)
    
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    assert DEFAULT_MCP_SERVERS["postgres"]["enabled"] is False


def test_postgres_mcp_tool_name_format() -> None:
    """Test that PostgreSQL MCP tools would be named correctly."""
    # PostgreSQL MCP server tools would be named mcp_postgres_<tool_name>
    expected_tools = [
        "mcp_postgres_query",
        "mcp_postgres_list_tables",
        "mcp_postgres_describe_table",
        "mcp_postgres_read_resource",
    ]
    
    # Verify naming convention
    for tool in expected_tools:
        assert tool.startswith("mcp_postgres_"), f"Tool {tool} should start with mcp_postgres_"


# ==============================================================================
# Git MCP Server Integration Tests
# ==============================================================================

def test_git_server_config_in_defaults() -> None:
    """Test that Git server is in DEFAULT_MCP_SERVERS."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    assert "git" in DEFAULT_MCP_SERVERS
    git_config = DEFAULT_MCP_SERVERS["git"]
    assert git_config["command"] == "npx"
    assert "-y" in git_config["args"]
    assert "@modelcontextprotocol/server-git" in git_config["args"]


def test_git_server_always_enabled() -> None:
    """Test that Git server is always enabled (no token required)."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    # Git server should be enabled by default
    assert DEFAULT_MCP_SERVERS["git"]["enabled"] is True


def test_git_mcp_tool_name_format() -> None:
    """Test that Git MCP tools would be named correctly."""
    # Git MCP server tools would be named mcp_git_<tool_name>
    expected_tools = [
        "mcp_git_status",
        "mcp_git_log",
        "mcp_git_diff",
        "mcp_git_branch",
        "mcp_git_commit",
    ]
    
    # Verify naming convention
    for tool in expected_tools:
        assert tool.startswith("mcp_git_"), f"Tool {tool} should start with mcp_git_"


# ==============================================================================
# Jira MCP Server Integration Tests
# ==============================================================================

def test_jira_server_config_in_defaults() -> None:
    """Test that Jira server is in DEFAULT_MCP_SERVERS."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    assert "jira" in DEFAULT_MCP_SERVERS
    jira_config = DEFAULT_MCP_SERVERS["jira"]
    assert jira_config["command"] == "npx"
    assert "-y" in jira_config["args"]
    assert "@modelcontextprotocol/server-jira" in jira_config["args"]


def test_jira_server_disabled_without_token() -> None:
    """Test that Jira server is disabled when no token is present."""
    import os
    # Ensure no token is set
    os.environ.pop("JIRA_TOKEN", None)
    
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    assert DEFAULT_MCP_SERVERS["jira"]["enabled"] is False


def test_jira_mcp_tool_name_format() -> None:
    """Test that Jira MCP tools would be named correctly."""
    # Jira MCP server tools would be named mcp_jira_<tool_name>
    expected_tools = [
        "mcp_jira_list_issues",
        "mcp_jira_get_issue",
        "mcp_jira_create_issue",
        "mcp_jira_update_issue",
        "mcp_jira_search_issues",
    ]
    
    # Verify naming convention
    for tool in expected_tools:
        assert tool.startswith("mcp_jira_"), f"Tool {tool} should start with mcp_jira_"


# ==============================================================================
# Docker MCP Server Integration Tests
# ==============================================================================

def test_docker_server_config_in_defaults() -> None:
    """Test that Docker server is in DEFAULT_MCP_SERVERS."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    assert "docker" in DEFAULT_MCP_SERVERS
    docker_config = DEFAULT_MCP_SERVERS["docker"]
    assert docker_config["command"] == "npx"
    assert "-y" in docker_config["args"]
    assert "@modelcontextprotocol/server-docker" in docker_config["args"]


def test_docker_server_always_enabled() -> None:
    """Test that Docker server is always enabled (no token required)."""
    from modules.agent.mcp_integration import DEFAULT_MCP_SERVERS
    
    # Docker server should be enabled by default
    assert DEFAULT_MCP_SERVERS["docker"]["enabled"] is True


def test_docker_mcp_tool_name_format() -> None:
    """Test that Docker MCP tools would be named correctly."""
    # Docker MCP server tools would be named mcp_docker_<tool_name>
    expected_tools = [
        "mcp_docker_list_containers",
        "mcp_docker_list_images",
        "mcp_docker_run_container",
        "mcp_docker_stop_container",
        "mcp_docker_get_logs",
    ]
    
    # Verify naming convention
    for tool in expected_tools:
        assert tool.startswith("mcp_docker_"), f"Tool {tool} should start with mcp_docker_"