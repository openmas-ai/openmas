# MCP Integration Guide

This guide explains how to use OpenMAS with MCP (Model Context Protocol) version 1.7.1. MCP is a protocol that enables standardized communication between language models, tools, and other services.

## MCP 1.7.1 Features

OpenMAS integrates with MCP 1.7.1, which provides:

- Stable SSE transport implementation
- Robust connection resilience and error handling
- Efficient serialization of complex data types
- Comprehensive support for tool calling with error handling

## Prerequisites

To use MCP with OpenMAS, you need to install the `mcp` package:

```bash
poetry add mcp==1.7.1
```

Or if you're installing OpenMAS with poetry:

```bash
poetry install --extras mcp
```

## Supported Transports

MCP supports two primary transport mechanisms:

1. **SSE (Server-Sent Events)** - Used for HTTP-based communication between agents
2. **STDIO** - Used for direct pipe-based communication, typically for local processes

## Creating MCP Communicators

### SSE Communicator (Server Mode)

```python
from openmas.communication.mcp.sse_communicator import McpSseCommunicator

# Create a server-mode communicator
communicator = McpSseCommunicator(
    agent_name="tool_provider",
    service_urls={},  # Server doesn't need service URLs
    server_mode=True,
    http_port=8081,  # Optional: specify a port (defaults to 8080)
)
```

### SSE Communicator (Client Mode)

```python
from openmas.communication.mcp.sse_communicator import McpSseCommunicator

# Create a client-mode communicator
communicator = McpSseCommunicator(
    agent_name="tool_user",
    service_urls={"service_name": "http://localhost:8081"},
    server_mode=False,  # Client mode
)
```

### STDIO Communicator

```python
from openmas.communication.mcp.stdio_communicator import McpStdioCommunicator

# Create a STDIO communicator
communicator = McpStdioCommunicator(
    agent_name="tool_provider",
    service_urls={},  # Not used for STDIO
)
```

## Registering and Using Tools

### Registering a Tool (Server-side)

```python
async def process_text_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Process text by converting to uppercase and counting words."""
    # Get the input text from the payload
    text = payload.get("text", "")

    # Process the text
    processed_text = text.upper()
    word_count = len(text.split())

    # Return the result
    return {
        "processed_text": processed_text,
        "word_count": word_count,
        "status": "success"
    }

# Register the tool with the communicator
await communicator.register_tool(
    name="process_text",
    description="Process text input by converting to uppercase and counting words",
    function=process_text_handler,
)
```

### Calling a Tool (Client-side)

```python
# Create a payload for the tool
payload = {
    "text": "Hello, this is a test message.",
    # Optionally add a content field in MCP 1.7.1 format
    "content": [{"type": "text", "text": "Hello, this is a test message."}],
}

# Call the tool
result = await communicator.call_tool(
    target_service="tool_provider",
    tool_name="process_text",
    arguments=payload,
    timeout=10.0,  # Optional timeout in seconds
)
```

## Error Handling

MCP 1.7.1 provides improved error handling. Here's how to handle errors properly:

```python
from openmas.exceptions import CommunicationError

try:
    result = await communicator.call_tool(
        target_service="tool_provider",
        tool_name="process_text",
        arguments=payload,
    )
    # Process successful result
except asyncio.TimeoutError:
    # Handle timeout
    print("Tool call timed out")
except CommunicationError as e:
    # Handle communication error
    print(f"Communication error: {e}")
except Exception as e:
    # Handle other errors
    print(f"Unexpected error: {e}")
```

## Complete Example

See the following examples for complete implementations:

1. **SSE Example**: `examples/example_08_mcp/01_mcp_sse_tool_call/`
2. **STDIO Example**: `examples/example_08_mcp/02_mcp_stdio_tool_call/`

## Best Practices

1. **Proper Initialization**: Always initialize and start your communicator before using it.
2. **Error Handling**: Add appropriate error handling for all tool calls.
3. **Resource Cleanup**: Ensure proper cleanup of resources with try/finally blocks.
4. **Timeout Handling**: Set appropriate timeouts for tool calls to prevent hanging.
5. **Graceful Shutdown**: Always shut down communicators properly when your agent stops.

## Known Limitations

1. SSE connections can be sensitive to network issues - implement retry logic for production systems.
2. The `test_openmas_mcp_sse_integration` test is currently skipped due to SSE endpoint compatibility issues.
3. The `test_concurrent_sse_connections` test is skipped due to asyncio event loop issues that need to be addressed.

## Troubleshooting

1. **404 Not Found errors**: Ensure the server is running and the URL is correct.
2. **Connection refused**: Check that the server is running and the port is correct.
3. **Event loop is closed errors**: These can occur during cleanup. They're typically harmless but indicate a resource wasn't closed properly.

## Future Improvements

1. Enhanced resilience for SSE connections with automatic reconnection.
2. Better handling of concurrent connections.
3. More comprehensive end-to-end tests.
