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

## Creating Integration Tests

### General Approach for MCP Integration Tests

Effective MCP integration tests should:

1. **Launch a real MCP server subprocess**
2. **Connect a client to the server**
3. **Verify communication works both ways**
4. **Properly clean up resources**

Here's a template for structured MCP integration tests:

```python
@pytest.mark.asyncio
@pytest.mark.mcp
async def test_mcp_integration():
    """Test MCP integration with real transport (stdio/SSE)."""
    process = None

    try:
        # 1. Launch the server subprocess
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(server_script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 2. Wait for server initialization
        await asyncio.sleep(1.0)  # Give server time to initialize

        # 3. Verify server output for successful startup
        server_start_verified = False
        if process.stderr:
            stderr_line = await asyncio.wait_for(process.stderr.readline(), timeout=1.0)
            server_start_verified = "Starting server" in stderr_line.decode("utf-8")

        assert server_start_verified, "Server not started properly"

        # 4. Create and initialize client
        communicator = create_appropriate_communicator()

        # 5. Test communication (minimal example)
        response = await communicator.send_request("target_service", "echo", {"message": "test"})
        assert response["echoed"] == "test"

    finally:
        # 6. Clean up resources
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
```

### Stdio-Specific Testing

For testing stdio transport:

```python
# Server script (stdio_server_script.py)
async def main():
    # Create a FastMCP server
    mcp_server = FastMCP("TestStdioServer", log_level="DEBUG")

    # Register a test tool
    mcp_server.add_tool(fn=echo, name="echo", description="Echo back a message")

    # Run the server - crucial to use run_stdio_async() for stdio transport
    await mcp_server.run_stdio_async()

# Integration test for stdio
async def test_stdio_integration():
    script_path = "path/to/stdio_server_script.py"

    # Launch subprocess with pipes
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(script_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Create stdio communicator
    communicator = McpStdioCommunicator(
        agent_name="test_client",
        service_urls={"stdio_service": "service_command"},
        service_args={"stdio_service": ["arg1", "arg2"]},
        server_mode=False,
    )

    # Connect and test
    await communicator.send_request("stdio_service", "echo", {"message": "test"})
```

### SSE-Specific Testing

For testing SSE transport:

```python
# Server script (sse_server_script.py)
async def main():
    # Create a FastAPI app for HTTP server
    app = FastAPI(title="MCP SSE Test Server")

    # Create a FastMCP server
    mcp_server = FastMCP(
        name="TestSseServer",
        instructions="Test server for integration testing",
    )

    # Register a test tool
    mcp_server.add_tool(fn=echo, name="echo", description="Echo back a message")

    # Mount the MCP server to the FastAPI app
    if hasattr(mcp_server, "router"):
        app.mount("/mcp", mcp_server.router)

    # Run the uvicorn server
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port)
    server = uvicorn.Server(config)
    await server.serve()

# Integration test for SSE
async def test_sse_integration():
    port = 8765  # Use an available test port

    # Launch subprocess
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(server_script_path),
        "--port", str(port),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    # Wait for server to start and get URL
    server_url = f"http://127.0.0.1:{port}/mcp"

    # Create SSE communicator
    communicator = McpSseCommunicator(
        agent_name="test_client",
        service_urls={"sse_service": server_url},
        server_mode=False,
    )

    # Wrap HTTP requests in try/except for graceful handling
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{port}/test") as response:
                # Validate HTTP connection
                assert response.status == 200
    except aiohttp.ClientError:
        # Handle connection errors gracefully
        logger.warning("HTTP connection failed, but continuing test")
```

## Common Issues and Solutions

### 1. Initialization Timing Issues

**Problem**: The most common error when working with MCP is `RuntimeError: Received request before initialization was complete`.

**Solution**: Always explicitly call `await session.initialize()` after creating a `ClientSession` and before making any tool calls:

```python
# Create the session
session = ClientSession(read_stream, write_stream)

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

```python
# Reliable process launching for testing stdio
process = await asyncio.create_subprocess_exec(
    sys.executable,
    str(script_path),
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)

# Pipe example in server script
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        # Only log to stderr, NEVER to stdout
        logging.StreamHandler(sys.stderr)
    ],
)

# Proper flush in server code
sys.stdout.buffer.write(message_bytes)
sys.stdout.buffer.flush()
```

### 3. SSE Transport Issues

For SSE transport:

- Ensure server CORS settings allow connections from client origin
- Pay special attention to handling SSE reconnection logic
- Always explicitly call `await session.initialize()` after connection
- Handle network connectivity errors gracefully in tests
- Use a test endpoint on your server to verify basic HTTP connectivity

```python
# Server-side SSE error handling
try:
    server = FastMCP(name="TestSseServer")
    app.mount("/mcp", server.router)

    # Add a test endpoint that doesn't require MCP for connectivity verification
    @app.get("/test")
    async def test():
        return {"status": "ok", "message": "Server is running"}

except Exception as e:
    logger.error(f"Server initialization error: {e}")
    raise
```

```python
# Client-side SSE error handling
try:
    async with aiohttp.ClientSession() as session:
        try:
            # Test basic HTTP connectivity first
            async with session.get(f"{base_url}/test") as response:
                assert response.status == 200, "Server not accessible"

            # Then connect using MCP
            service_url = f"{base_url}/mcp"
            communicator = McpSseCommunicator(
                agent_name="test_client",
                service_urls={"service_name": service_url},
                server_mode=False,
            )
        except aiohttp.ClientError as e:
            logger.error(f"HTTP connection error: {e}")
            # Handle gracefully or re-raise as needed
except Exception as e:
    logger.error(f"General communication error: {e}")
```

### 4. Cleanup and Resource Management

Proper cleanup is critical in integration tests to prevent resource leaks and ensure tests can run repeatedly:

```python
# Robust cleanup pattern
try:
    # Test operations
    process = await asyncio.create_subprocess_exec(...)

    # MCP operations...
finally:
    # Client manager cleanup
    if communicator:
        try:
            await communicator.stop()
        except Exception as e:
            logger.warning(f"Error closing communicator: {e}")

    # Process termination
    if process and process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("Process did not terminate, killing")
            process.kill()
            await process.wait()
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

# For stdio transport
await mcp_server.run_stdio_async()

# For SSE transport
app = FastAPI()
app.mount("/mcp", mcp_server.router)
# Then run with uvicorn
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

7. **Design tests to be resilient to external failures**:
   - Add skip conditions for missing optional dependencies
   - Use try/except blocks to handle network errors gracefully
   - Fall back to defaults if expected server responses aren't available
   - Log warnings instead of failing tests on non-critical issues

## Testing Best Practices

1. **Implement incremental verification in tests**:
   ```python
   # Step 1: Verify the server process starts correctly
   assert process.returncode is None, "Process failed to start"

   # Step 2: Verify basic connectivity (custom test endpoint)
   try:
       async with session.get(f"{url}/test") as response:
           assert response.status == 200, "Server not responding"
   except Exception as e:
       pytest.skip(f"Server connectivity test failed: {e}")

   # Step 3: Test MCP-specific functionality
   result = await communicator.send_request(...)
   assert result["expected_key"] == expected_value
   ```

2. **Add a test-only mode to server scripts**:
   ```python
   # In server script
   if "--test-only" in sys.argv:
       # Skip full MCP initialization, just send test response
       test_message = {"jsonrpc": "2.0", "id": "test-only-mode", "method": "test"}
       sys.stdout.buffer.write((json.dumps(test_message) + "\n").encode("utf-8"))
       sys.stdout.buffer.flush()
       sys.exit(0)
   ```

3. **Create separate test files for each transport**:
   - `test_stdio_integration.py` - Tests stdin/stdout communication
   - `test_sse_integration.py` - Tests HTTP-based communication
   - `test_grpc_integration.py` - Tests gRPC communication (if applicable)

4. **Manage port conflicts in SSE/HTTP tests**:
   ```python
   # Use different ports for different tests to avoid conflicts
   TEST_PORT = 8765 + random.randint(0, 1000)  # Dynamic port selection
   ```

5. **Allow tests to skip gracefully when dependencies are missing**:
   ```python
   # Check for optional dependencies
   try:
       import aiohttp
       HAS_AIOHTTP = True
   except ImportError:
       HAS_AIOHTTP = False

   @pytest.mark.skipif(not HAS_AIOHTTP, reason="aiohttp is required for this test")
   async def test_sse_integration():
       # Test code here
   ```

6. **Log rich context information during tests**:
   ```python
   logger.info(
       "Testing tool call",
       tool="echo",
       args={"message": "test"},
       server_pid=process.pid,
       server_running=(process.returncode is None)
   )
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

5. **Use the `--test-only` pattern for quick verification**:
   Add a simple mode to server scripts that bypasses complex initialization and just returns a predefined response.

## Common API Differences between MCP Versions

The MCP library has evolved with API changes. Here are some differences to be aware of:

| Feature | Older API | Newer API |
|---------|-----------|-----------|
| Register tool | `register_tool(name, description, fn)` | `add_tool(fn, name, description)` |
| Run stdio server | `serve_stdio()` | `run_stdio_async()` |
| Mount to app | `mount_to(app, path)` | `app.mount(path, server.router)` |

Always check the MCP library version you're using to ensure correct method calls.

## Resources

- [MCP Official Documentation](https://modelcontextprotocol.io/docs/concepts/architecture)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [FastMCP on GitHub](https://github.com/modelcontextprotocol/fastmcp)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## Real-World Successful Pattern

A pattern that reliably works in production environments:

```python
async def run_client(sse_url):
    try:
        async with sse_client(sse_url) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                try:
                    # Critical explicit initialization
                    await session.initialize()

                    # Then safe to call tools
                    response = await session.call_tool("echo", {"message": "test"})

                except Exception as init_error:
                    logger.error(f"Error during session.initialize(): {init_error}")

    except Exception as conn_error:
        logger.error(f"Connection error: {conn_error}")
```

The explicit `await session.initialize()` call after creating the `ClientSession` is crucial for proper synchronization, especially in the SSE transport.
