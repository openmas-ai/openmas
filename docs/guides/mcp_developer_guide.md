# MCP v1.7.1 Developer Guide (OpenMAS Integration)

**Version:** 2.0 (Based on `mcp` Python SDK v1.7.1)

## 1. Introduction

**MCP stands for Model Context Protocol.** Developed by Anthropic, it provides a standardized interface for AI models and services to communicate, enabling features like tool use, resource sharing, and prompting across different transport layers.

**Goal:** This document serves as the definitive guide for developers working with MCP (specifically `mcp` Python SDK v1.7.1) within the OpenMAS framework. It outlines best practices, setup instructions, server/client implementation patterns, testing strategies, and solutions to common issues encountered during integration.

**Target Audience:** Developers building or integrating MCP-based agents, tools, or communication components in OpenMAS.

**Key MCP Concepts:**
*   **Transport:** The underlying protocol for communication (e.g., stdio, SSE).
*   **Server (`FastMCP`):** Hosts tools and resources.
*   **Client (`ClientSession`):** Connects to a server to use tools/resources.
*   **Tools:** Functions exposed by a server for clients to call.
*   **Streams:** Underlying communication channels managed by the transport layer.

**Official Resources:**
*   **Concepts & Architecture:** [https://modelcontextprotocol.io/docs/concepts/architecture](https://modelcontextprotocol.io/docs/concepts/architecture)
*   **Python SDK (GitHub):** [https://github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)
*   **MCP Documentation:** [https://modelcontextprotocol.io/docs/](https://modelcontextprotocol.io/docs/)

---

## 2. Setup

1.  **Install `mcp`:** Use `poetry` (or `pip`) to add the `mcp` package. For CLI tools like the inspector, include the `cli` extra:
    ```bash
    poetry add "mcp[cli]>=1.7.1"
    # or
    # pip install "mcp[cli]>=1.7.1"
    ```

2.  **Dependencies for SSE:** If using the SSE transport, ensure `aiohttp` and `httpx` are installed (they are typically included as dependencies of `mcp`, but verify):
    ```bash
    poetry add aiohttp httpx
    # or
    # pip install aiohttp httpx
    ```

---

## 3. Creating an MCP Server (`FastMCP`)

The server exposes tools that clients can call.

### 3.1. Basic Server Setup

```python
# Example: src/my_mcp_server.py
import asyncio
import logging
import sys
import json
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import TextContent

# Configure logging (stderr is often useful for debugging subprocesses)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("MyMCPServer")

# Create the FastMCP instance
mcp_server = FastMCP(
    name="MyExampleServer",
    log_level="DEBUG", # Use DEBUG for detailed MCP logs
)
```

### 3.2. Defining Tools

Tools are async functions that can be added to the FastMCP server.

```python
# Define a simple echo tool
async def echo_tool(ctx: Context) -> list[TextContent]:
    """
    Simple echo tool.

    Args:
        ctx: The MCP context object containing request information.

    Returns:
        A list of TextContent objects.
    """
    logger.debug(f"Echo tool called with context: {ctx}")

    # Extract the message from context
    message = None
    if hasattr(ctx, "arguments") and ctx.arguments:
        if "message" in ctx.arguments:
            message = ctx.arguments["message"]
        elif "content" in ctx.arguments and isinstance(ctx.arguments["content"], list):
            # Handle content array format
            for item in ctx.arguments["content"]:
                if isinstance(item, dict) and "text" in item:
                    message = item["text"]
                    break

    if message is None:
        logger.error("No message found in context")
        return [TextContent(type="text", text=json.dumps({"error": "No message found"}))]

    try:
        # Prepare the success payload
        response_obj = {"echoed": message}
        return [TextContent(type="text", text=json.dumps(response_obj))]
    except Exception as e:
        logger.error(f"Error in echo tool: {e}", exc_info=True)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

# Add the tool to the server
mcp_server.add_tool(
    name="echo",
    description="Echo back the input message as JSON",
    fn=echo_tool,
)

# Add more tools as needed...
```

**Key Points for Tools (v1.7.1):**
*   **Return Value:** Tools must return a list of TextContent objects. For simple text responses, wrap your string in a TextContent object.
*   **Context Handling:** The context object now has an `arguments` attribute that contains the request parameters.
*   **Error Handling:** Return error messages as TextContent objects rather than raising exceptions, as exceptions won't be properly formatted for clients.

---

## 4. Running the MCP Server

How you run the server depends on the desired transport.

### 4.1. SSE Transport (Recommended for Networked Agents)

With MCP 1.7.1, running an SSE server is simpler and more reliable.

```python
# Example: src/my_mcp_server.py (continued)

import uvicorn
from fastapi import FastAPI

# --- FastAPI Integration ---

# 1. Create a FastAPI app instance
app = FastAPI(title="My MCP Server", version="1.0")

# 2. Mount the FastMCP server at /sse endpoint
app = mcp_server.mount_to_app(app)

# Optional: Add a root endpoint for basic health check
@app.get("/", tags=["General"])
async def read_root():
    return {"message": "MCP SSE Server is running. Connect via /sse."}

# --- Main Execution ---

async def start_server(host="127.0.0.1", port=8765):
    """Configures and runs the Uvicorn server."""
    logger.info("Configuring Uvicorn...")
    config = uvicorn.Config(
        app=app, # Run the FastAPI app instance
        host=host,
        port=port,
        log_level="debug" # Use debug for detailed Uvicorn/ASGI logs
    )
    server = uvicorn.Server(config)

    # **CRITICAL for Testing:** Print the URL *before* starting the server
    # Allows test harnesses to know where to connect.
    sys.stderr.write(f"SSE_SERVER_URL=http://{host}:{port}\n")
    sys.stderr.flush()

    logger.info(f"Starting Uvicorn server for FastAPI+MCP on {host}:{port}")
    await server.serve() # This blocks until shutdown

if __name__ == "__main__":
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run MCP SSE server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on")
    args = parser.parse_args()

    logger.info("Starting main function")
    try:
        asyncio.run(start_server(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.error(f"Unhandled exception in top-level: {e}", exc_info=True)
        sys.exit(1)
```

**Running the SSE Server:**
```bash
python src/my_mcp_server.py --host 0.0.0.0 --port 8000
```

### 4.2. Stdio Transport (For Local Inter-Process Communication)

For stdio transport, the approach is similar to previous versions:

```python
# Example: src/my_mcp_server.py (modified main section)

# (Keep FastMCP instance and tool definitions from above)

async def start_stdio_server():
    """Runs the MCP server over stdio."""
    # Signal readiness BEFORE running the server loop
    # Use stderr for signals, as stdout is used for MCP JSON messages
    sys.stderr.write("STDIO_SERVER_READY\n")
    sys.stderr.flush()

    logger.info("Starting MCP server over stdio")
    try:
        await mcp_server.run_stdio()
    except Exception as e:
        logger.error(f"Error in stdio server: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
        try:
            asyncio.run(start_stdio_server())
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down stdio server")
        except Exception as e:
            logger.error(f"Unhandled exception in stdio server: {e}", exc_info=True)
            sys.exit(1)
    else:
        # Default to SSE server
        # (SSE server code from previous section)
```

**Running the Stdio Server:**
```bash
python src/my_mcp_server.py --stdio
```

---

## 5. Creating an MCP Client

Clients connect to servers and call tools.

### 5.1. SSE Client

```python
# Example: src/my_mcp_client.py
import asyncio
import logging
import sys
import json

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("MyMCPClient")

async def call_echo_tool(server_url: str, message: str, timeout: float = 30.0):
    """Call the echo tool on the server.

    Args:
        server_url: URL of the SSE server, e.g., http://localhost:8765/sse
        message: Message to echo
        timeout: Timeout in seconds
    """
    logger.info(f"Connecting to server: {server_url}")

    try:
        # Connect to the SSE server
        async with sse_client(server_url) as (read_stream, write_stream):
            # Create a session
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the session
                logger.info("Initializing session")
                await asyncio.wait_for(session.initialize(), timeout=timeout)
                logger.info("Session initialized successfully")

                # Call the echo tool
                logger.info(f"Calling echo tool with message: {message}")
                result = await asyncio.wait_for(
                    session.call_tool("echo", {"message": message}),
                    timeout=timeout
                )

                # Check for errors
                if result.isError:
                    logger.error(f"Tool call failed: {result}")
                    print(f"Error: {result}")
                    return

                # Process the response
                if result.content and len(result.content) > 0:
                    response_text = result.content[0].text
                    try:
                        response_data = json.loads(response_text)
                        logger.info(f"Got response: {response_data}")
                        print(f"Echo response: {response_data}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse response JSON: {response_text}")
                        print(f"Invalid response: {response_text}")
                else:
                    logger.warning("Empty response from server")
                    print("Empty response")

    except asyncio.TimeoutError:
        logger.error(f"Operation timed out after {timeout} seconds")
        print(f"Error: Timeout after {timeout} seconds")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"Error: {e}")

async def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="MCP SSE Client")
    parser.add_argument("--server", default="http://localhost:8765/sse", help="Server URL")
    parser.add_argument("--message", default="Hello World", help="Message to echo")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout in seconds")
    args = parser.parse_args()

    # Call the echo tool
    await call_echo_tool(args.server, args.message, args.timeout)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down client")
    except Exception as e:
        logger.error(f"Unhandled exception in top-level: {e}", exc_info=True)
        sys.exit(1)
```

### 5.2. Stdio Client

```python
# Example: src/my_mcp_stdio_client.py
import asyncio
import logging
import sys
import json
import subprocess
from typing import Tuple, Optional

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("MyMCPStdioClient")

async def start_server_process(server_cmd: list[str]) -> Tuple[subprocess.Popen, bool]:
    """Start the server process and wait for it to be ready.

    Args:
        server_cmd: Command to start the server

    Returns:
        Tuple of (process, is_ready)
    """
    logger.info(f"Starting server process: {' '.join(server_cmd)}")

    # Start the server process
    process = subprocess.Popen(
        server_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,  # Binary mode for better pipe handling
    )

    # Wait for the ready signal on stderr
    is_ready = False
    ready_timeout = 10.0  # seconds

    async def read_stderr():
        nonlocal is_ready
        while process.poll() is None:  # While process is running
            try:
                line = process.stderr.readline()
                if line:
                    line_str = line.decode('utf-8', errors='replace').strip()
                    logger.debug(f"Server stderr: {line_str}")
                    if "STDIO_SERVER_READY" in line_str:
                        logger.info("Server signaled ready")
                        is_ready = True
                        break
            except Exception as e:
                logger.error(f"Error reading stderr: {e}")
                break

    # Run stderr reader with timeout
    stderr_task = asyncio.create_task(read_stderr())
    try:
        await asyncio.wait_for(stderr_task, timeout=ready_timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Timed out waiting for server ready signal after {ready_timeout}s")
        # Continue anyway, as the server might still be usable

    # Check if the process is still running
    if process.poll() is not None:
        logger.error(f"Server process exited prematurely with code {process.returncode}")
        return process, False

    return process, is_ready

async def call_echo_tool_stdio(server_cmd: list[str], message: str, timeout: float = 30.0):
    """Call the echo tool using stdio transport.

    Args:
        server_cmd: Command to start the server
        message: Message to echo
        timeout: Timeout in seconds
    """
    # Start the server process
    process, is_ready = await start_server_process(server_cmd)

    if not is_ready:
        logger.warning("Server may not be ready, but attempting to connect anyway")

    try:
        # Connect to the stdio server
        logger.info("Connecting to stdio server")
        async with stdio_client(process.stdout, process.stdin) as (read_stream, write_stream):
            # Create a session
            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the session
                logger.info("Initializing session")
                await asyncio.wait_for(session.initialize(), timeout=timeout)
                logger.info("Session initialized successfully")

                # Call the echo tool
                logger.info(f"Calling echo tool with message: {message}")
                result = await asyncio.wait_for(
                    session.call_tool("echo", {"message": message}),
                    timeout=timeout
                )

                # Check for errors
                if result.isError:
                    logger.error(f"Tool call failed: {result}")
                    print(f"Error: {result}")
                    return

                # Process the response
                if result.content and len(result.content) > 0:
                    response_text = result.content[0].text
                    try:
                        response_data = json.loads(response_text)
                        logger.info(f"Got response: {response_data}")
                        print(f"Echo response: {response_data}")
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse response JSON: {response_text}")
                        print(f"Invalid response: {response_text}")
                else:
                    logger.warning("Empty response from server")
                    print("Empty response")

    except asyncio.TimeoutError:
        logger.error(f"Operation timed out after {timeout} seconds")
        print(f"Error: Timeout after {timeout} seconds")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"Error: {e}")
    finally:
        # Terminate the server process
        if process.poll() is None:  # If still running
            logger.info("Terminating server process")
            process.terminate()
            try:
                process.wait(timeout=5.0)  # Wait for graceful termination
            except subprocess.TimeoutExpired:
                logger.warning("Server process did not terminate gracefully, killing")
                process.kill()

async def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="MCP Stdio Client")
    parser.add_argument("--server-cmd", default="python src/my_mcp_server.py --stdio",
                        help="Command to start the server")
    parser.add_argument("--message", default="Hello World", help="Message to echo")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout in seconds")
    args = parser.parse_args()

    # Call the echo tool
    server_cmd = args.server_cmd.split()
    await call_echo_tool_stdio(server_cmd, args.message, args.timeout)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down client")
    except Exception as e:
        logger.error(f"Unhandled exception in top-level: {e}", exc_info=True)
        sys.exit(1)
```

---

## 6. OpenMAS Integration

OpenMAS provides a high-level abstraction over MCP through its communicator classes.

### 6.1. Using McpSseCommunicator

```python
from openmas.communication.mcp.sse_communicator import McpSseCommunicator

# Server mode
server_communicator = McpSseCommunicator(
    agent_name="tool_provider",
    service_urls={},  # Server doesn't need service URLs
    server_mode=True,
    http_port=8080,
    http_host="0.0.0.0",
    server_instructions="A service that provides text processing tools",
)

# Register a tool
await server_communicator.register_tool(
    name="process_text",
    description="Process text by converting to uppercase and counting words",
    function=async_process_text_handler,
)

# Client mode
client_communicator = McpSseCommunicator(
    agent_name="tool_user",
    service_urls={"tool_provider": "http://localhost:8080/sse"},
    server_mode=False,
)

# Call a tool
result = await client_communicator.call_tool(
    target_service="tool_provider",
    tool_name="process_text",
    arguments={"text": "Hello, world!"},
    timeout=10.0,
)
```

### 6.2. Using McpStdioCommunicator

```python
from openmas.communication.mcp.stdio_communicator import McpStdioCommunicator

# Server mode
server_communicator = McpStdioCommunicator(
    agent_name="tool_provider",
    service_urls={},  # Server doesn't need service URLs
)

# Register a tool
await server_communicator.register_tool(
    name="process_text",
    description="Process text by converting to uppercase and counting words",
    function=async_process_text_handler,
)

# Client mode (assumes server is started separately)
client_communicator = McpStdioCommunicator(
    agent_name="tool_user",
    service_urls={"tool_provider": "python -m agents.tool_provider.agent"},
)

# Call a tool
result = await client_communicator.call_tool(
    target_service="tool_provider",
    tool_name="process_text",
    arguments={"text": "Hello, world!"},
    timeout=10.0,
)
```

---

## 7. Best Practices for MCP 1.7.1

### 7.1. Tool Implementation

1. **Return Format**: Always return a list of TextContent objects.
2. **Error Handling**: Handle errors within the tool and return appropriate error messages as TextContent rather than raising exceptions.
3. **Argument Extraction**: Be flexible when extracting arguments from the context - check both direct arguments and content arrays.
4. **Logging**: Add detailed logging to aid debugging.

### 7.2. Connection Management

1. **Timeouts**: Always use timeouts for network operations to prevent hanging.
2. **Graceful Shutdown**: Properly close connections and stop servers to prevent resource leaks.
3. **Connection Pooling**: For high-traffic applications, consider implementing connection pooling.
4. **Error Recovery**: Implement retry logic for transient errors.

### 7.3. Testing

1. **Mock Testing**: Use `MockCommunicator` for unit tests.
2. **Integration Testing**: Create real network tests for end-to-end validation.
3. **Test Harnesses**: Build test harnesses that simulate different failure modes.
4. **Logging Verification**: Verify log outputs to ensure proper operation.

---

## 8. Troubleshooting

### 8.1. Common Issues

1. **Connection Timeouts**: Check firewall settings and ensure the server is running.
2. **Tool Not Found**: Verify that the tool is registered with the exact name you're trying to call.
3. **Argument Format Errors**: Ensure you're passing the correct argument format.
4. **Event Loop Errors**: These can occur during cleanup and are typically harmless but indicate a resource wasn't closed properly.

### 8.2. Debugging Techniques

1. **Enable DEBUG Logging**: Set logging level to DEBUG to see detailed info about MCP operations.
2. **Use MCP Inspector**: The MCP CLI includes an inspector tool for debugging.
3. **Check Network Traffic**: Use tools like Wireshark to inspect network traffic for SSE transport.
4. **Validate JSON**: Ensure all JSON payloads are valid.

---

## 9. Advanced Topics

### 9.1. Concurrent Tool Calls

MCP 1.7.1 improves handling of concurrent connections. Here's a pattern for making concurrent tool calls:

```python
async def call_tools_concurrently(communicator, target_service, tools_and_args):
    """Call multiple tools concurrently.

    Args:
        communicator: The MCP communicator
        target_service: Target service name
        tools_and_args: List of (tool_name, arguments) tuples

    Returns:
        Dictionary mapping tool names to results
    """
    # Create tasks for each tool call
    tasks = {
        tool_name: asyncio.create_task(
            communicator.call_tool(
                target_service=target_service,
                tool_name=tool_name,
                arguments=args,
            )
        )
        for tool_name, args in tools_and_args
    }

    # Wait for all tasks to complete
    results = {}
    for tool_name, task in tasks.items():
        try:
            results[tool_name] = await task
        except Exception as e:
            results[tool_name] = {"error": str(e)}

    return results
```

### 9.2. Custom Transport Implementation

If you need a custom transport mechanism beyond SSE and stdio, you can implement your own transport:

1. Create classes that implement the `ReadStream` and `WriteStream` interfaces.
2. Implement a client connector function similar to `sse_client` or `stdio_client`.
3. Create a server transport similar to `SseServerTransport`.

---

## 10. Future Directions

MCP continues to evolve. Here are some areas to watch:

1. **Better Error Handling**: Improved error handling and reporting.
2. **Enhanced Tool Argument Schema**: More robust tool argument validation.
3. **WebSocket Transport**: Potential support for WebSocket as an alternative to SSE.
4. **Performance Optimizations**: Ongoing improvements to connection handling and message serialization.

Keep an eye on the official MCP documentation and GitHub repositories for updates.

---

## 11. Further Resources

- [Complete MCP Documentation](https://modelcontextprotocol.io/docs/)
- [MCP Python SDK GitHub](https://github.com/modelcontextprotocol/python-sdk)
- [OpenMAS MCP Integration Guide](/guides/mcp_integration.md)
- [MCP SSE Tool Call Tutorial](/guides/mcp_sse_tool_call_tutorial.md)
- [MCP Stdio Tool Call Tutorial](/guides/mcp_stdio_tool_call_tutorial.md)
