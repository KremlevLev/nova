# modules/agent/mcp_integration.py
"""MCP Integration Bootstrap.

Connects MCP servers and registers their tools with the existing tool registry.
Supports environment-based configuration for tokens and database paths.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from modules.agent.mcp_gateway import MCPGateway, MCPServerConfig

logger = logging.getLogger("MCPIntegration")


def _get_env_tokens() -> dict[str, str]:
    """Load MCP server tokens from environment variables."""
    return {
        "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", ""),
        "SLACK_TOKEN": os.environ.get("SLACK_TOKEN", ""),
        "GOOGLE_DRIVE_TOKEN": os.environ.get("GOOGLE_DRIVE_TOKEN", ""),
        "JIRA_TOKEN": os.environ.get("JIRA_TOKEN", ""),
    }


def _get_sqlite_path() -> str:
    """Get SQLite database path from environment."""
    return os.environ.get("MCP_SQLITE_PATH", "nova_memory.db")


def _get_postgres_connection_string() -> str:
    """Get PostgreSQL connection string from environment."""
    return os.environ.get("MCP_POSTGRES_CONNECTION", "")


async def initialize_mcp_servers(
    gateway: MCPGateway,
    registry: Any,
    *,
    auto_discover: bool = False,
) -> int:
    """
    Initialize MCP servers and register their tools.
    
    Args:
        gateway: MCPGateway instance
        registry: ToolRegistry to register tools with
        auto_discover: If True, discover localhost MCP servers
        
    Returns:
        Number of MCP tools registered
    """
    # Initialize the gateway to discover tools
    result = await gateway.initialize()
    logger.info("MCP initialization: %s", result.message)
    
    # Register MCP tools with the registry
    count = await gateway.register_with_registry(registry)
    logger.info("Registered %d MCP tools with registry", count)
    
    return count


def create_mcp_gateway_from_config(config: dict[str, Any]) -> MCPGateway:
    """
    Create MCP Gateway from configuration dict.
    
    Expected config format:
    {
        "mcp": {
            "github": {
                "command": "node",
                "args": ["@modelcontextprotocol/server-github"],
                "env": {"GITHUB_TOKEN": "token"}
            }
        }
    }
    """
    gateway = MCPGateway()
    
    mcp_config = config.get("mcp", {})
    
    for name, server_config in mcp_config.items():
        try:
            config_obj = MCPServerConfig(
                name=name,
                command=server_config.get("command", ""),
                args=server_config.get("args", []),
                env=server_config.get("env", {}),
                enabled=server_config.get("enabled", True),
            )
            gateway.register_server(config_obj)
        except Exception as exc:
            logger.warning(
                "Failed to register MCP server %s: %s",
                name,
                exc,
            )
    
    return gateway


# Default MCP servers for common use cases
DEFAULT_MCP_SERVERS: dict[str, dict[str, Any]] = {
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {},  # Will be populated from GITHUB_TOKEN env var
        "enabled": False,  # Will be True if GITHUB_TOKEN is available
    },
    "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "--directory", "."],
        "env": {},
        "enabled": True,
    },
    "sqlite": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite"],
        "env": {},
        "enabled": False,  # Will be True if MCP_SQLITE_PATH is set
    },
    "slack": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "env": {},  # Will be populated from SLACK_TOKEN env var
        "enabled": False,  # Will be True if SLACK_TOKEN is available
    },
    "websearch": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-web-search"],
        "env": {},  # No token required for basic web search
        "enabled": True,  # Always enabled for web search capability
    },
    "gdrive": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-gdrive"],
        "env": {},  # Will be populated from GOOGLE_DRIVE_TOKEN env var
        "enabled": False,  # Will be True if GOOGLE_DRIVE_TOKEN is available
    },
    "postgres": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "env": {},  # Will be populated from MCP_POSTGRES_CONNECTION env var
        "enabled": False,  # Will be True if MCP_POSTGRES_CONNECTION is set
    },
    "git": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-git"],
        "env": {},  # No token required for local git operations
        "enabled": True,  # Always enabled for git operations
    },
    "jira": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-jira"],
        "env": {},  # Will be populated from JIRA_TOKEN env var
        "enabled": False,  # Will be True if JIRA_TOKEN is available
    },
    "docker": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-docker"],
        "env": {},  # No token required for local Docker operations
        "enabled": True,  # Always enabled for Docker operations
    },
}


async def bootstrap_mcp_from_defaults(
    registry: Any,
) -> MCPGateway:
    """
    Bootstrap MCP with default servers.
    
    Automatically enables servers based on available environment tokens.
    - GitHub: enabled if GITHUB_TOKEN is set
    - Filesystem: always enabled
    - SQLite: enabled if MCP_SQLITE_PATH is set
    - Slack: enabled if SLACK_TOKEN is set
    - Websearch: always enabled
    - Gdrive: enabled if GOOGLE_DRIVE_TOKEN is set
    - Postgres: enabled if MCP_POSTGRES_CONNECTION is set
    - Git: always enabled
    - Jira: enabled if JIRA_TOKEN is set
    - Docker: always enabled
    """
    gateway = MCPGateway()
    env_tokens = _get_env_tokens()
    sqlite_path = _get_sqlite_path()
    postgres_conn = _get_postgres_connection_string()
    
    for name, server_config in DEFAULT_MCP_SERVERS.items():
        # Determine if server should be enabled
        should_enable = server_config.get("enabled", False)
        
        # Override based on environment tokens
        if name == "github" and env_tokens.get("GITHUB_TOKEN"):
            should_enable = True
        elif name == "slack" and env_tokens.get("SLACK_TOKEN"):
            should_enable = True
        elif name == "sqlite" and os.environ.get("MCP_SQLITE_PATH"):
            should_enable = True
        elif name == "gdrive" and env_tokens.get("GOOGLE_DRIVE_TOKEN"):
            should_enable = True
        elif name == "postgres" and postgres_conn:
            should_enable = True
        elif name == "jira" and env_tokens.get("JIRA_TOKEN"):
            should_enable = True
        
        if should_enable:
            # Build env dict from server config + environment tokens
            env = {}
            if name == "github" and env_tokens.get("GITHUB_TOKEN"):
                env["GITHUB_TOKEN"] = env_tokens["GITHUB_TOKEN"]
            if name == "slack" and env_tokens.get("SLACK_TOKEN"):
                env["SLACK_TOKEN"] = env_tokens["SLACK_TOKEN"]
            if name == "gdrive" and env_tokens.get("GOOGLE_DRIVE_TOKEN"):
                env["GOOGLE_DRIVE_TOKEN"] = env_tokens["GOOGLE_DRIVE_TOKEN"]
            if name == "postgres" and postgres_conn:
                env["MCP_POSTGRES_CONNECTION"] = postgres_conn
            if name == "jira" and env_tokens.get("JIRA_TOKEN"):
                env["JIRA_TOKEN"] = env_tokens["JIRA_TOKEN"]
            
            # Build args for SQLite with path
            args = server_config["args"].copy()
            if name == "sqlite" and os.environ.get("MCP_SQLITE_PATH"):
                # Add --db-path argument for SQLite server
                args.extend(["--db-path", sqlite_path])
            
            # Merge with any existing env from config
            env.update(server_config.get("env", {}))
            
            config_obj = MCPServerConfig(
                name=name,
                command=server_config["command"],
                args=args,
                env=env,
                enabled=True,
            )
            gateway.register_server(config_obj)
            logger.info(
                "MCP server '%s' enabled with env token: %s",
                name,
                "yes" if env else "no",
            )
    
    await gateway.initialize()
    await gateway.register_with_registry(registry)
    
    return gateway