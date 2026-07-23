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
    url: str = ""  # For SSE transport


class MCPConnectionPool:
    """
    Pool for reusing MCP server processes.
    
    Maintains a pool of active subprocess connections for stdio transports
    to avoid process spawn overhead on each tool call.
    """
    
    def __init__(self, max_connections: int = 5) -> None:
        self._max_connections = max_connections
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._locks: dict[str, asyncio.Lock] = {}
    
    async def get_process(
        self,
        config: MCPServerConfig,
    ) -> asyncio.subprocess.Process | None:
        """
        Get or create a process for the given server config.
        
        Returns None if process is not available or failed.
        """
        if config.transport != "stdio":
            return None
        
        name = config.name
        
        # Check if process exists and is running
        if name in self._processes:
            process = self._processes[name]
            if process.returncode is None:
                return process
        
        # Create new process
        try:
            process = await asyncio.create_subprocess_exec(
                config.command,
                *config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**asyncio.get_event_loop().run_in_executor(None, lambda: __import__('os').environ), **config.env},
            )
            self._processes[name] = process
            self._locks[name] = asyncio.Lock()
            return process
        except Exception as exc:
            logger.warning(
                "Failed to create MCP process pool entry for %s: %s",
                name,
                exc,
            )
            return None
    
    async def call_tool_via_pool(
        self,
        config: MCPServerConfig,
        request: dict[str, Any],
        timeout: float = 30.0,
    ) -> tuple[dict[str, Any], str]:
        """
        Call a tool using pooled process.
        
        Returns (response_dict, stderr_output).
        """
        name = config.name
        
        # Get lock for this server
        lock = self._locks.get(name)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[name] = lock
        
        async with lock:
            process = await self.get_process(config)
            if process is None:
                raise RuntimeError(f"Cannot get process for MCP server {name}")
            
            # For pooled processes, we need to manage stdin/stdout carefully
            # Each request-response is a single call on the same process
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(
                        input=json.dumps(request).encode(),
                    ),
                    timeout=timeout,
                )
                
                response = json.loads(stdout.decode())
                return response, stderr.decode()
                
            except asyncio.TimeoutError:
                # Terminate stuck process
                process.kill()
                del self._processes[name]
                raise
            except json.JSONDecodeError:
                # Invalid response - recreate process
                process.kill()
                del self._processes[name]
                raise
    
    def close(self) -> None:
        """Close all pooled processes."""
        for name, process in list(self._processes.items()):
            if process is not None:
                try:
                    process.terminate()
                except (ProcessLookupError, AttributeError):
                    pass
        self._processes.clear()
        self._locks.clear()


class MCPGateway:
    """
    Gateway for connecting to MCP servers.
    
    Supports stdio and SSE transports for tool integration.
    Discovers tools and provides them for recovery operations.
    """
    
    def __init__(self, pool_size: int = 5) -> None:
        self._servers: dict[str, MCPServerConfig] = {}
        self._tool_schemas: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._initialized = False
        self._pool = MCPConnectionPool(max_connections=pool_size)
    
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
        Discover tools from an MCP server.
        
        Supports both stdio and SSE transports.
        Sends 'tools/list' request and returns tool schemas.
        """
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        }
        
        if config.transport == "sse":
            return await self._discover_tools_sse(config, request)
        else:
            return await self._discover_tools_stdio(config, request)

    async def _discover_tools_stdio(
        self,
        config: MCPServerConfig,
        request: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Discover tools using stdio transport."""
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

    async def _discover_tools_sse(
        self,
        config: MCPServerConfig,
        request: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Discover tools using SSE transport."""
        import aiohttp
        
        if not config.url:
            raise ValueError(f"SSE transport requires 'url' for server {config.name}")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Send initialization request
                async with session.post(
                    config.url,
                    json=request,
                    timeout=aiohttp.ClientTimeout(total=10.0),
                ) as response:
                    if response.status != 200:
                        raise RuntimeError(
                            f"SSE server returned status {response.status}"
                        )
                    
                    data = await response.json()
                    
                    if "error" in data:
                        raise RuntimeError(f"MCP SSE error: {data['error']}")
                    
                    return data.get("tools", [])
                    
        except asyncio.TimeoutError:
            raise RuntimeError(f"MCP SSE server {config.name} timed out")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid MCP SSE response: {exc}")
        except ImportError:
            raise RuntimeError("aiohttp required for SSE transport: pip install aiohttp")

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
            if config.transport == "sse":
                return await self._call_tool_sse(config, request, actual_tool_name)
            else:
                return await self._call_tool_stdio(config, request, actual_tool_name)
                
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

    async def _call_tool_stdio(
        self,
        config: MCPServerConfig,
        request: dict[str, Any],
        tool_name: str,
    ) -> ToolResult:
        """Call tool using stdio transport."""
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
                f"Tool {tool_name} failed: {response['error']}",
            )
        
        result = response.get("result", {})
        return ToolResult.ok(
            result.get("message", "Success"),
            data=result.get("data", {}),
        )

    async def _call_tool_sse(
        self,
        config: MCPServerConfig,
        request: dict[str, Any],
        tool_name: str,
    ) -> ToolResult:
        """Call tool using SSE transport."""
        import aiohttp
        
        if not config.url:
            return ToolResult.failure(
                "MCP_CONFIG_ERROR",
                "SSE transport requires 'url' in config",
            )
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                config.url,
                json=request,
                timeout=aiohttp.ClientTimeout(total=30.0),
            ) as response:
                data = await response.json()
                
                if "error" in data:
                    return ToolResult.failure(
                        "MCP_TOOL_ERROR",
                        f"Tool {tool_name} failed: {data['error']}",
                    )
                
                result = data.get("result", {})
                return ToolResult.ok(
                    result.get("message", "Success"),
                    data=result.get("data", {}),
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