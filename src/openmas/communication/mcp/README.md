# MCP Communication Module for OpenMAS

This module provides implementations of the `BaseCommunicator` interface using the [MCP (Message Channel Protocol)](https://github.com/anthropics/anthropic-sdk-python) from Anthropic. It enables OpenMAS agents to communicate with MCP-based services and provide MCP interfaces themselves.

## Components

### McpStdioCommunicator

A communicator that uses the MCP protocol over stdin/stdout:

- **Client Mode**: Connects to MCP services via subprocesses using stdin/stdout for communication
- **Server Mode**: Runs as an MCP server that communicates via stdin/stdout

### McpSseCommunicator

A communicator that uses the MCP protocol over HTTP with Server-Sent Events (SSE):

- **Client Mode**: Connects to MCP services over HTTP using SSE for communication
- **Server Mode**: Runs as an MCP server that provides an HTTP endpoint for SSE communication (using FastAPI)

### McpServerWrapper

A utility class to easily create MCP servers that can be run independently (not as part of an agent):

- Provides methods to add tools, resources, and prompts
- Supports both stdio and SSE transport mechanisms
- Useful for creating standalone MCP services

## Usage Examples

### McpStdioCommunicator in Client Mode

```python
from openmas import Agent
from openmas.communication.mcp import McpStdioCommunicator

# Create a communicator that connects to a subprocess running an MCP server
communicator = McpStdioCommunicator(
    agent_name="client_agent",
    service_urls={
        "mcp_service": "python -m service_script.py"  # Command to run the service
    }
)

# Create an agent with this communicator
agent = Agent(name="client_agent", communicator=communicator)

# Use the agent to communicate with the MCP service
await agent.start()
result = await agent.send_request(
    target_service="mcp_service",
    method="tool/call",
    params={"name": "some_tool", "arguments": {"param1": "value1"}}
)
await agent.stop()
```

### McpStdioCommunicator in Server Mode

```python
from openmas import Agent
from openmas.communication.mcp import McpStdioCommunicator

# Create a communicator that runs as an MCP server
communicator = McpStdioCommunicator(
    agent_name="server_agent",
    service_urls={},  # Not used in server mode
    server_mode=True,
    server_instructions="This is an MCP server that provides tools for analysis."
)

# Create an agent with this communicator
agent = Agent(name="server_agent", communicator=communicator)

# Register handlers that will be exposed as MCP tools
@agent.handler("analyze_data")
async def analyze_data(params):
    data = params.get("data", [])
    # Do some analysis
    return {"result": "Analysis complete", "stats": {"count": len(data)}}

# Start the agent to begin serving MCP requests
await agent.start()
```

### McpSseCommunicator in Client Mode

```python
from openmas import Agent
from openmas.communication.mcp import McpSseCommunicator

# Create a communicator that connects to HTTP endpoints with SSE
communicator = McpSseCommunicator(
    agent_name="client_agent",
    service_urls={
        "mcp_service": "http://localhost:8000/mcp"  # URL of the MCP SSE endpoint
    }
)

# Create an agent with this communicator
agent = Agent(name="client_agent", communicator=communicator)

# Use the agent to communicate with the MCP service
await agent.start()
result = await agent.send_request(
    target_service="mcp_service",
    method="tool/call",
    params={"name": "some_tool", "arguments": {"param1": "value1"}}
)
await agent.stop()
```

### McpSseCommunicator in Server Mode

```python
from fastapi import FastAPI
from openmas import Agent
from openmas.communication.mcp import McpSseCommunicator

# Create a FastAPI app (optional, will create one if not provided)
app = FastAPI(title="MCP Server")

# Create a communicator that runs as an MCP server over HTTP/SSE
communicator = McpSseCommunicator(
    agent_name="server_agent",
    service_urls={},  # Not used in server mode
    server_mode=True,
    http_port=8000,
    server_instructions="This is an MCP server that provides tools for analysis.",
    app=app  # Optional FastAPI app
)

# Create an agent with this communicator
agent = Agent(name="server_agent", communicator=communicator)

# Register handlers that will be exposed as MCP tools
@agent.handler("analyze_data")
async def analyze_data(params):
    data = params.get("data", [])
    # Do some analysis
    return {"result": "Analysis complete", "stats": {"count": len(data)}}

# Start the agent to begin serving MCP requests via HTTP
await agent.start()
```

### Standalone MCP Server with McpServerWrapper

```python
from openmas.communication.mcp import McpServerWrapper

# Create a server wrapper
server = McpServerWrapper(
    name="analysis_server",
    instructions="This server provides data analysis tools."
)

# Add tools using decorators
@server.tool(name="analyze_data", description="Analyze the provided data")
async def analyze_data(data):
    # Process the data
    return {"result": "Analysis complete", "count": len(data)}

# Add a resource
@server.resource(uri="/data/sample", name="Sample Data")
async def get_sample_data():
    return {"data": [1, 2, 3, 4, 5]}

# Run the server (blocking call)
server.run(transport="stdio")  # or "sse" for HTTP/SSE
```

## Implementation Details

### Mapping OpenMAS to MCP

OpenMAS uses a JSON-RPC-like protocol for communication, which differs from MCP's tool/prompt/resource-based model. The communicators provide a mapping between these models:

| OpenMAS Concept | MCP Equivalent | Notes |
|-------------------|----------------|-------|
| `send_request`    | `call_tool`    | Maps method patterns like `tool/call` to appropriate MCP SDK calls |
| `send_notification` | Async `call_tool` | Creates a task that doesn't await the result |
| `register_handler` | `add_tool`    | Registers handlers as MCP tools |

### Special Method Patterns

The communicators recognize certain method patterns to provide more specific functionality:

- `tool/list`: List available tools from a service
- `tool/call`: Call a specific tool
- `prompt/list`: List available prompts
- `prompt/get`: Get a prompt response
- `resource/list`: List available resources
- `resource/read`: Read a resource's content

For other methods, the method name is used as the tool name in MCP.

## Error Handling

The communicators provide standardized error handling, mapping MCP errors to OpenMAS exceptions:

- Connection failures: `CommunicationError`
- Missing services: `ServiceNotFoundError`
- Tool execution errors: `CommunicationError` with details

## Dependencies

These communicators require the `mcp` package from Anthropic:

```bash
poetry add mcp
```

For the SSE communicator in server mode, you also need FastAPI and Uvicorn:

```bash
poetry add fastapi uvicorn
```
