# MCP Integration with SimpleMAS

This document explains how to use the Anthropic MCP SDK (Model Context Protocol) with SimpleMAS.

## Overview

The MCP SDK from Anthropic provides a client and server implementation for the Model Context Protocol (MCP), which enables AI models to access various capabilities like tools, resources, and prompts.

SimpleMAS provides adapters to use MCP with SimpleMAS agents:

- `McpClientAdapter`: Adapter for SimpleMAS agents to connect to MCP services
- `McpServerWrapper`: Wrapper for hosting MCP servers within SimpleMAS agents

## Installation

1. Install the MCP SDK:

```bash
pip install mcp==1.6.0
```

2. Install SimpleMAS with the adapters (already included in the SimpleMAS package)

## Client Usage

To use MCP as a client in a SimpleMAS agent:

```python
from simple_mas.agent import Agent
from simple_mas.config import AgentConfig
from simple_mas.communication.mcp import McpClientAdapter
from simple_mas.logging import get_logger

# Create a MCP client adapter
communicator = McpClientAdapter(
    agent_name="MyAgent",
    service_urls={"service_name": "command_or_url"},
    use_sse=False  # Use SSE (True) or stdio (False)
)

# Create and run the agent
config = AgentConfig(name="MyAgent")
agent = Agent(config=config, communicator=communicator)

await agent.start()
await agent.run()
await agent.stop()
```

### MCP Client Methods

The `McpClientAdapter` provides methods for interacting with MCP services:

- **Tools**
  - `list_tools(service_name)`: List available tools
  - `call_tool(service_name, tool_name, arguments)`: Call a tool

- **Prompts**
  - `list_prompts(service_name)`: List available prompts
  - `get_prompt(service_name, prompt_name, arguments)`: Get a prompt

- **Resources**
  - `list_resources(service_name)`: List available resources
  - `list_resource_templates(service_name)`: List available resource templates
  - `read_resource(service_name, uri)`: Read a resource

## Server Usage

To create a MCP server in a SimpleMAS agent:

```python
from simple_mas.agent import Agent
from simple_mas.config import AgentConfig
from simple_mas.communication.mcp import McpServerWrapper

# Create a MCP server wrapper
server = McpServerWrapper(
    name="MyServer",
    instructions="Instructions for the server"
)

# Define tools
@server.tool(description="My tool description")
async def my_tool(param: str) -> str:
    return f"Result: {param}"

# Define prompts
@server.prompt(description="My prompt description")
async def my_prompt(param: str) -> List[Message]:
    # Return a list of Message objects
    pass

# Define resources
@server.resource("resource://example", description="My resource description")
async def my_resource() -> str:
    return "Resource content"

# Run the server
server.run("stdio")  # or "sse" for SSE transport
```

## Examples

Check out the example implementations:

- **Client**: `mcp_client_example.py` - SimpleMAS agent using MCP client
- **Server**: `mcp_server_example.py` - SimpleMAS agent hosting a MCP server
- **Service**: `llm_service/main.py` - MCP service that agents can connect to

## Running the Examples

### Running the LLM Service

```bash
python examples/llm_service/main.py
```

### Running the Client Example

```bash
python examples/mcp_client_example.py
```

### Running the Server Example

```bash
python examples/mcp_server_example.py
```

## Transport Options

MCP supports two transport protocols:

1. **stdio**: Uses standard input/output for communication (default)
2. **SSE (Server-Sent Events)**: Uses HTTP with Server-Sent Events for communication

To use SSE transport:

```python
# For client
communicator = McpClientAdapter(
    agent_name="MyAgent",
    service_urls={"service_name": "http://localhost:8000"},
    use_sse=True
)

# For server
server.run("sse")
```

## Resources

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Model Context Protocol Documentation](https://docs.anthropic.com/claude/docs/model-context-protocol)
