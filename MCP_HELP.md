# Model Context Protocol (MCP) - Usage Guide and Troubleshooting

## Introduction

The Model Context Protocol (MCP) is a standardized interface for interacting with AI models. This document captures key insights, best practices, and troubleshooting steps discovered during implementation and debugging of MCP-based systems.

## Core Concepts

MCP provides a standardized way to:
- Call tools (functions) on remote services
- Exchange prompts and sample from models
- Share resources across services
- Create transport-agnostic AI agent systems

## Key Components

### Transport Protocols

MCP supports multiple transports:

1. **stdio** - Process-to-process communication using standard input/output
2. **SSE** (Server-Sent Events) - HTTP-based unidirectional streaming
3. **gRPC** - High-performance bidirectional streaming (when available)

### Primary Classes

#### Client-Side
- `ClientSession` - Main interface for client-side MCP operations
- `stdio_client` - Factory function for stdio transport
- `sse_client` - Factory function for SSE transport

#### Server-Side
- `FastMCP` - The main server implementation for hosting MCP services
- `Context` - Contains context for handling tools and operations

## Common Issues and Solutions

### 1. Initialization Timing Issues

**Problem**: The most common error when working with MCP is `RuntimeError: Received request before initialization was complete`.

**Solution**: Always explicitly call `await session.initialize()` after creating a `ClientSession` and before making any tool calls:

```python
# Create the session
session = ClientSession(read_stream, write_stream)
await session.__aenter__()

# CRITICAL: Always explicitly initialize
await session.initialize()

# Wait a short time for the server to process the initialization
await asyncio.sleep(1.0)

# Now safe to proceed with tool calls
result = await session.call_tool("some_tool", {"arg": "value"})
```

### 2. stdio Transport Issues

When using stdio transport:

- Ensure correct pipe configuration (stdin/stdout properly connected)
- Handle process lifecycle carefully (start, terminate)
- Use `asyncio.subprocess.PIPE` for both stdin and stdout
- Log server errors to stderr, never stdout (reserved for protocol messages)
- Always flush stdout after writing to ensure data is sent immediately

### 3. SSE Transport Issues

For SSE transport:

- Ensure server CORS settings allow connections from client origin
- Pay special attention to handling SSE reconnection logic
- Always explicitly call `await session.initialize()` after connection

### 4. Cleanup and Resource Management

Proper cleanup is critical:

```python
# Client manager cleanup
try:
    await client_manager.__aexit__(None, None, None)
except Exception as e:
    logger.warning(f"Error closing client manager: {e}")

# Process termination
if process.returncode is None:
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Process did not terminate, killing")
        process.kill()
```

## Working with FastMCP Server

### Creating and Running a Server

```python
# Create the server
mcp_server = FastMCP("MyServer", log_level="DEBUG")

# Register tools
mcp_server.add_tool(
    fn=my_tool_function,
    name="my_tool",
    description="Description of what my tool does"
)

# Run the server over stdio
await mcp_server.run_stdio_async()
```

### Tool Function Signature

Tool functions must follow this signature:

```python
async def my_tool(ctx: Context, param1: str, param2: int) -> CallToolResult:
    # Process the request
    result = do_something(param1, param2)
    return CallToolResult({"key": result})
```

## Working with ClientSession

### Creating a Session

```python
# For stdio transport
params = StdioServerParameters(command=command, args=args)
client_manager = stdio_client(params)
read_stream, write_stream = await client_manager.__aenter__()
session = ClientSession(read_stream, write_stream)
await session.__aenter__()
await session.initialize()  # Critical!

# For SSE transport
async with sse_client(sse_url) as streams:
    read_stream, write_stream = streams
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()  # Critical!
        # Now you can call tools
```

### Calling Tools

```python
# List available tools
tools = await session.list_tools()

# Call a tool
result = await session.call_tool(
    "tool_name",
    arguments={"param1": "value1", "param2": 42}
)
```

## Best Practices

1. **Always explicitly initialize sessions**:
   ```python
   await session.initialize()
   ```

2. **Use proper error handling and retries for initialization**:
   ```python
   max_retries = 2
   retry_count = 0

   while retry_count <= max_retries:
       try:
           await session.initialize()
           break
       except RuntimeError as e:
           if "initialization was complete" in str(e) and retry_count < max_retries:
               retry_count += 1
               await asyncio.sleep(1.0 + (retry_count * 0.5))
           else:
               raise
   ```

3. **Separate protocol communication from application logic**:
   - Keep protocol messages on stdout/stdin
   - Send logs/debug info only to stderr

4. **Implement robust cleanup to prevent resource leaks**:
   - Use `try/finally` blocks to ensure cleanup
   - Implement timeouts for operations
   - Properly terminate subprocesses

5. **Handle timeouts gracefully**:
   ```python
   try:
       result = await asyncio.wait_for(
           session.call_tool("tool_name", arguments),
           timeout=10.0
       )
   except asyncio.TimeoutError:
       # Handle timeout
   ```

6. **Shield critical cleanup operations from cancellation**:
   ```python
   try:
       await asyncio.shield(communicator.stop())
   except Exception as e:
       logger.warning(f"Error during cleanup: {e}")
   ```

## Debugging Tips

1. **Enable detailed logging**:
   ```python
   logging.basicConfig(
       level=logging.DEBUG,
       format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
       handlers=[logging.StreamHandler(sys.stderr)]
   )
   ```

2. **Log important protocol events**:
   ```python
   logger.debug(f"Sending message: {json.dumps(message)}")
   logger.debug(f"Received response: {response}")
   ```

3. **Inspect raw protocol messages**:
   - Add a simple test mode to print a test message directly to stdout
   - Use a Python script to directly handle stdin/stdout communication

4. **Create minimal reproduction cases**:
   - Isolate protocol issues with standalone scripts
   - Test server scripts with direct subprocess calls

## Common API Differences between MCP Versions

The MCP library has evolved with API changes. Here are some differences to be aware of:

| Feature | Older API | Newer API |
|---------|-----------|-----------|
| Register tool | `register_tool(name, description, fn)` | `add_tool(fn, name, description)` |
| Run stdio server | `serve_stdio()` | `run_stdio_async()` |

Always check the MCP library version you're using to ensure correct method calls.

## Testing Strategies

1. **Test each transport layer separately**:
   - Create tests specific to stdio, SSE, etc.

2. **Implement integration tests with actual server processes**:
   - Test full communication cycle
   - Verify proper initialization and tool calls

3. **Use timeouts for all asynchronous operations**:
   ```python
   await asyncio.wait_for(operation(), timeout=10.0)
   ```

4. **Add direct process communication tests**:
   - Verify raw protocol message exchange
   - Test initialization, tool listing, and tool calls

## Resources

- [MCP Official Documentation](https://modelcontextprotocol.io/docs/concepts/architecture)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [FastMCP on GitHub](https://github.com/modelcontextprotocol/fastmcp)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## Common Issues
Just wanted to confirm that I was also encountering the exact same RuntimeError: Received request before initialization was complete error on the server side when using a Python client based on mcp.client.sse.sse_client and mcp.client.session.ClientSession to connect to a FastMCP server over SSE.

Similar to others, the error occurred when the client attempted its first session.call_tool() request after establishing the connection.

Debugging attempts like adding asyncio.sleep() delays (even up to 10 seconds) after creating the ClientSession did not resolve the issue. For reasons that now are obvious (we need to smash the supergateway bug)

Following the suggestion from @altmind 's experience, adding an explicit await session.initialize() call immediately after the ClientSession is created solved the problem reliably.

Here's the structure that worked for my client script:

Python

import asyncio
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
# ... other imports

async def run_client(sse_url):
    try:
        async with sse_client(sse_url) as streams:
            print("SSE connection established.")
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                print("ClientSession created.")
                try:
                    print("--> Calling session.initialize()...")
                    await session.initialize() # <----- Explicit call added here!!!
                    print("<-- session.initialize() completed.")

                    # Now safe to proceed with tool calls
                    print("Session initialized, safe to call tools.")
                    # Example tool call:
                    # response = await session.call_tool("some_tool", {"arg": "value"})
                    # print(f"Tool response: {response}")

                except Exception as init_error:
                    print(f"Error during session.initialize(): {init_error}")

    except Exception as conn_error:
        print(f"Connection error: {conn_error}")

# Example usage:
# asyncio.run(run_client("http://your-server-url/sse"))
As of today, it seems explicit initialization via await session.initialize() is crucial for proper synchronization when using the Python client SDK over SSE.

Hope this confirmation helps others debugging this issue!
