# MCP Integration Guide for Nova Agent

This guide describes how to add new features via MCP (Model Context Protocol) following the project rules.

## Quick Start

### 1. Find MCP Server

Check if there's a ready MCP server in the ecosystem:
- https://github.com/modelcontextprotocol/servers
- npm registry for `@modelcontextprotocol/*` packages

### 2. Configuration Example

Create a server configuration in `.env`:

```json
{
  "mcp": {
    "github": {
      "command": "node",
      "args": ["path/to/github-mcp-server"],
      "env": {
        "GITHUB_TOKEN": "your_token_here"
      }
    },
    "database": {
      "command": "python",
      "args": ["path/to/database-mcp-server"],
      "env": {
        "DATABASE_URL": "your_connection_string"
      }
    }
  }
}
```

### 3. Python Integration Code

```python
# Register MCP server for recovery
from modules.agent.mcp_gateway import MCPGateway, MCPServerConfig
from modules.agent.recovery import set_mcp_recovery_tools

gateway = MCPGateway()

# Register server
config = MCPServerConfig(
    name="github",
    command="node",
    args=["github-mcp-server"],
    env={"GITHUB_TOKEN": "your_token"},
)
gateway.register_server(config)

# Initialize and get tools
result = await gateway.initialize()
mcp_tools = gateway.get_available_tools()

# Register for recovery
set_mcp_recovery_tools(mcp_tools)
```

### 4. Using MCP Tools in Recovery

```python
from modules.agent.mcp_gateway import MCPGateway
from modules.agent.recovery import GracefulDegradation, SelfDiagnostics

# Create diagnostics and degradation
diagnostics = SelfDiagnostics()
degradation = GracefulDegradation(diagnostics)

# Check system health
mode = await degradation.update_mode()

if mode != "full":
    # Get alternative tools for degraded mode
    alternative_tools = degradation.get_alternative_tools()
    
    # Optionally use MCP fallback
    if degradation.should_use_mcp_fallback():
        mcp_tools = get_mcp_recovery_tools()
```

## MCP Server Examples

### GitHub Integration
```bash
# Available MCP servers for GitHub
npx @modelcontextprotocol/server-github
# Tools: create_issue, list_issues, get_issue, search_repos, etc.
```

### Database Integration
```bash
# SQLite MCP server
npm install -g @modelcontextprotocol/server-sqlite
# Tools: query, list_tables, describe_table, etc.
```

### Slack Integration
```bash
# Slack MCP server
npm install -g @modelcontextprotocol/server-slack
# Tools: post_message, list_channels, get_channel_messages, etc.
```

## Architecture

```
modules/
  agent/
    mcp_gateway.py    # MCP client implementation (stdio/SDE)
    recovery.py       # Recovery engine + SelfDiagnostics + GracefulDegradation
    
Application layer uses MCP tools by:
1. Initializing MCPGateway with server configs
2. Calling gateway.initialize() to discover tools
3. Injecting MCP tools into the tool registry
4. Using SelfDiagnostics to monitor health
5. Falling back to MCP tools when primary systems fail