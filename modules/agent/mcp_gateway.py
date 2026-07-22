# modules/agent/mcp_gateway.py
"""MCP Gateway for Recovery & Self-healing.

Provides integration with external MCP servers for:
- Automatic rollback via external tools
- Alternative paths discovery and execution
- Graceful degradation capabilities
- Self-diagnostics
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from modules.domain.results import ToolResult
from modules.tools.base import ToolCategory, RiskLevel

logger = logging.getLogger("MCPGateway")


@dataclass(slots=True)
class MCPServerConfig:
    """Configuration for MCP server connection."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    transport: str = "stdio"  # stdio or sse


class MCPGateway:
    """
    Gateway for connecting to MCP servers.
    
    Supports stdio and SSE transports for tool integration.
    Discovers tools and provides them for recovery operations.
    """
    
    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {}
        self._tool_schemas: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._initialized = False
    
    def register_server(
        self,
        config: MCPServerConfig,
    ) -> None:
        """Register an MCP server configuration."""
        self._servers[config.name] = config
        logger.info("Registered MCP server: %s", config.name)
    
    async def initialize(self) -> ToolResult:
        """Initialize all registered MCP servers and discover tools."""
        if self._initialized:
            return ToolResult.ok("MCP Gateway already initialized.")
        
        for name, config in self._servers.items():
            if config.enabled:
                try:
                    tools = await self._discover_tools(config)
                    for tool in tools:
                        tool_name = f"mcp_{name}_{tool.get('name', 'unknown')}"
                        self._tool_schemas[tool_name] = tool
                    logger.info(
                        "Discovered %d tools from MCP server: %s",
                        len(tools),
                        name,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to initialize MCP server %s: %s",
                        name,
                        exc,
                    )
        
        self._initialized = True
        return ToolResult.ok(
            f"MCP Gateway initialized with {len(self._tool_schemas)} tools.",
            data={"tool_count": len(self._tool_schemas)},
        )
    
    async def _discover_tools(
        self,
        config: MCPServerConfig,
    ) -> list[dict[str, Any]]:
        """
        Discover tools from an MCP server using stdio protocol.
        
        Sends 'tools/list' request and returns tool schemas.
        """
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        }
        
        try:
            process = await asyncio.create_subprocess_exec(
                config.command,
                *config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**asyncio.get_event_loop().run_in_executor(None, lambda: __import__('os').environ), **config.env},
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(
                    input=json.dumps(request).encode(),
                ),
                timeout=10.0,
            )
            
            if process.returncode != 0:
                raise RuntimeError(
                    f"MCP server exited with code {process.returncode}: "
                    f"{stderr.decode()}",
                )
            
            response = json.loads(stdout.decode())
            
            if "error" in response:
                raise RuntimeError(f"MCP error: {response['error']}")
            
            return response.get("tools", [])
            
        except asyncio.TimeoutError:
            raise RuntimeError(f"MCP server {config.name} timed out")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid MCP response: {exc}")
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """
        Call a tool from an MCP server.
        
        Args:
            tool_name: Full tool name (e.g., 'mcp_recovery_rollback')
            arguments: Tool arguments
            
        Returns:
            ToolResult with the tool execution result
        """
        # Parse server and tool name
        parts = tool_name.split("_", 2)
        if len(parts) < 3:
            return ToolResult.failure(
                "INVALID_TOOL_NAME",
                f"Invalid MCP tool name format: {tool_name}",
            )
        
        server_name = parts[1]
        actual_tool_name = parts[2]
        
        config = self._servers.get(server_name)
        if config is None:
            return ToolResult.failure(
                "UNKNOWN_MCP_SERVER",
                f"MCP server not found: {server_name}",
            )
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": actual_tool_name,
                "arguments": arguments,
            },
        }
        
        try:
            process = await asyncio.create_subprocess_exec(
                config.command,
                *config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(
                    input=json.dumps(request).encode(),
                ),
                timeout=30.0,
            )
            
            response = json.loads(stdout.decode())
            
            if "error" in response:
                return ToolResult.failure(
                    "MCP_TOOL_ERROR",
                    f"Tool {actual_tool_name} failed: {response['error']}",
                )
            
            result = response.get("result", {})
            return ToolResult.ok(
                result.get("message", "Success"),
                data=result.get("data", {}),
            )
            
        except asyncio.TimeoutError:
            return ToolResult.failure(
                "MCP_TIMEOUT",
                f"Tool {actual_tool_name} timed out",
                retryable=True,
            )
        except Exception as exc:
            return ToolResult.failure(
                "MCP_CONNECTION_ERROR",
                f"Failed to call MCP tool: {exc}",
                retryable=True,
            )
    
    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Get all discovered tool schemas for model consumption."""
        schemas = []
        for name, schema in self._tool_schemas.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": schema.get("description", ""),
                    "parameters": schema.get("parameters", {
                        "type": "object",
                        "properties": {},
                    }),
                },
            })
        return schemas
    
    def get_available_tools(self) -> set[str]:
        """Get set of available MCP tool names."""
        return set(self._tool_schemas.keys())
    
    async def register_with_registry(
        self,
        registry: Any,
    ) -> int:
        """
        Register MCP tools with ToolRegistry.
        
        Returns number of tools registered.
        """
        count = 0
        for tool_name, schema in self._tool_schemas.items():
            try:
                # Create sync handler wrapper that calls async method via asyncio
                def make_handler(name: str) -> Callable[..., Any]:
                    def handler(**kwargs) -> ToolResult:
                        return asyncio.run(self.call_tool(name, kwargs))
                    return handler
                
                self._handlers[tool_name] = make_handler(tool_name)
                
                # Register with registry
                registry.register(
                    schema={
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": schema.get("description", ""),
                            "parameters": schema.get("parameters", {
                                "type": "object",
                                "properties": {},
                            }),
                        },
                    },
                    handler=self._handlers[tool_name],
                )
                count += 1
            except ValueError:
                # Tool already registered
                pass
        
        return count


# Pre-defined MCP server configurations for recovery
DEFAULT_RECOVERY_SERVERS: list[MCPServerConfig] = [
    MCPServerConfig(
        name="recovery",
        command="python",
        args=["-m", "mcp_server_recovery"],
        env={"MCP_RECOVERY_MODE": "auto_rollback"},
        enabled=True,
    ),
]