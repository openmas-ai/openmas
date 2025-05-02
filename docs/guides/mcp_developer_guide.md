# MCP v1.6 Developer Guide (OpenMAS Integration)

**Version:** 1.0 (Based on `mcp` Python SDK v1.6.0)

## 1. Introduction

**MCP stands for Model Context Protocol.** Developed by Anthropic, it provides a standardized interface for AI models and services to communicate, enabling features like tool use, resource sharing, and prompting across different transport layers.

**Goal:** This document serves as the definitive guide for developers working with MCP (specifically `mcp` Python SDK v1.6.0 and `FastMCP`) within the OpenMAS framework. It outlines best practices, setup instructions, server/client implementation patterns, testing strategies, and solutions to common issues encountered during integration.

**Target Audience:** Developers building or integrating MCP-based agents, tools, or communication components in OpenMAS.

**Key MCP Concepts:**
*   **Transport:** The underlying protocol for communication (e.g., stdio, SSE).
*   **Server (`FastMCP`):** Hosts tools and resources.
*   **Client (`ClientSession`):** Connects to a server to use tools/resources.
*   **Tools:** Functions exposed by a server for clients to call.
*   **Streams:** Underlying communication channels managed by the transport layer.

**Official Resources:**
*   **Concepts & Architecture:** [https://modelcontextprotocol.io/docs/concepts/architecture](https://modelcontextprotocol.io/docs/concepts/architecture)
*   **Python SDK (GitHub):** [https://github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) (Check issues for potential problems)
*   **FastMCP Server (GitHub):** [https://github.com/modelcontextprotocol/fastmcp](https://github.com/modelcontextprotocol/fastmcp)

---

## 2. Setup

1.  **Install `mcp`:** Use `poetry` (or `pip`) to add the `mcp` package. For CLI tools like the inspector, include the `cli` extra:
    ```bash
    poetry add "mcp[cli]>=1.6.0,<1.7.0"
    # or
    # pip install "mcp[cli]>=1.6.0,<1.7.0"
    ```
    *Note: Pinning to `<1.7.0` is recommended as patterns might change in future versions.*

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
from mcp.types import CallToolResult, TextContent # Not typically needed for tool return

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

Tools are async functions decorated with `@mcp_server.tool()`.

```python
@mcp_server.tool(name="echo", description="Echo back the input message as JSON")
async def echo_tool(ctx: Context, message: any) -> str: # Return type is typically str (JSON)
    """
    Simple echo tool.

    Args:
        ctx: The MCP context (rarely needed for simple tools).
        message: The input message (can be any JSON-serializable type).

    Returns:
        A JSON string containing the echoed message.
    """
    logger.debug(f"Echo tool called with message: {message!r} (type: {type(message)})")
    try:
        # Prepare the success payload
        response_obj = {"echoed": message}
        json_response = json.dumps(response_obj)
        logger.debug(f"Returning echo response JSON: {json_response}")

        # **CRITICAL (MCP 1.6): Return the JSON string directly.**
        # Do NOT manually wrap in CallToolResult or TextContent.
        # FastMCP handles the wrapping during serialization.
        return json_response

    except Exception as e:
        logger.error(f"Error in echo tool: {e}", exc_info=True)

        # **CRITICAL (MCP 1.6): Re-raise exceptions.**
        # Do NOT try to manually format an error CallToolResult.
        # FastMCP will catch the exception and generate a standard error response.
        raise # Re-raise the original exception

# Add more tools as needed...
# @mcp_server.tool(...)
# async def another_tool(...): ...
```

**Key Points for Tools (v1.6):**
*   **Return Value:** Return simple, JSON-serializable types (like strings, dicts, lists, numbers). `FastMCP` automatically wraps successful string returns into `CallToolResult(content=[TextContent(type="text", text=...)])`. Returning complex objects directly might work if Pydantic serialization succeeds, but returning a JSON string is often safest. **Do not manually return `CallToolResult` or `TextContent` objects.**
*   **Error Handling:** Let exceptions propagate out of your tool function (or re-raise them). `FastMCP` will catch them and return a standardized error `CallToolResult` to the client. **Do not manually create and return error `CallToolResult` objects.**

---

## 4. Running the MCP Server

How you run the server depends on the desired transport.

### 4.1. SSE Transport (Recommended for Networked Agents)

**Challenge:** `FastMCP` v1.6.0 is *not* a fully self-contained ASGI application that works correctly out-of-the-box with servers like Uvicorn just by passing the `FastMCP` instance. `FastMCP.run(transport='sse')` or `run_sse_async` are also problematic.

**Solution:** Integrate `FastMCP` manually with a standard ASGI framework like `FastAPI`.

```python
# Example: src/my_mcp_server.py (continued)

import uvicorn
from fastapi import FastAPI, Request
from mcp.server.sse import SseServerTransport
from starlette.routing import Mount # Import Mount

# --- FastAPI Integration ---

# 1. Create a FastAPI app instance
app = FastAPI(title="My MCP Server via FastAPI", version="1.0")

# 2. Use the mcp_server instance created earlier

# 3. Create an SSE Transport instance
# The path here ("/messages/") is for the client POSTing messages back *to* the server.
sse_transport = SseServerTransport("/messages/")

# 4. Mount the POST handler for incoming client messages
# CRITICAL: This route allows the server to receive messages from the client session.
app.router.routes.append(Mount("/messages", app=sse_transport.handle_post_message))

# 5. Define the main /sse GET endpoint for establishing connections
@app.get("/sse", tags=["MCP"])
async def handle_sse_connection(request: Request):
    """
    Handles incoming SSE connection requests and runs the MCP protocol loop.
    """
    logger.info(f"Incoming SSE connection request from {request.client}")
    try:
        # sse_transport.connect_sse handles the SSE handshake & provides streams
        async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (
            read_stream,
            write_stream,
        ):
            logger.info("SSE connection established, running MCP server loop.")
            # Run the FastMCP server logic over the established streams
            await mcp_server._mcp_server.run(
                read_stream,
                write_stream,
                mcp_server._mcp_server.create_initialization_options(),
            )
            logger.info("MCP server loop finished for this connection.")
    except Exception as e:
        logger.error(f"Error during SSE handling: {e}", exc_info=True)
        # Depending on when the error occurs, a response might have already been sent.
        # Consider appropriate error handling/response if possible.
        raise # Re-raise for potential higher-level handling

# Optional: Add a root endpoint for basic health check
@app.get("/", tags=["General"])
async def read_root():
    return {"message": "MCP SSE Server via FastAPI is running. Connect via /sse."}

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
    sys.stderr.write(f"SSE_SERVER_URL=http://{host}:{port}\\n")
    sys.stderr.flush()

    logger.info(f"Starting Uvicorn server for FastAPI+MCP on {host}:{port}")
    await server.serve() # This blocks until shutdown

if __name__ == "__main__":
    # Example: Add arg parsing if needed
    # parser = argparse.ArgumentParser(...)
    # args = parser.parse_args()
    # host = args.host
    # port = args.port
    host = "127.0.0.1"
    port = 8765

    logger.info("Starting main function")
    try:
        asyncio.run(start_server(host, port))
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.error(f"Unhandled exception in top-level: {e}", exc_info=True)
        sys.exit(1)

```

**Running the SSE Server:**
```bash
python src/my_mcp_server.py --host 0.0.0.0 --port 8000 # Example
```

**Helpful Article:** The integration pattern above was heavily influenced by the approach detailed in this article, which helped resolve persistent 500 errors when directly using `FastMCP` as the ASGI app:
*   [Implementing MCP(FastMCP) in a FastAPI Application - uselessai.in](https://uselessai.in/implementing-mcp-architecture-in-a-fastapi-application-f513989b65d9)

### 4.2. Stdio Transport (For Local Inter-Process Communication)

This is simpler as `FastMCP` provides a dedicated method.

```python
# Example: src/my_mcp_server.py (modified main section)

# (Keep FastMCP instance and tool definitions from above)

async def start_stdio_server():
    """Runs the MCP server over stdio."""
    # **CRITICAL for Testing:** Signal readiness BEFORE running the server loop.
    # Use stderr for signals, as stdout is used for MCP JSON messages.
    sys.stderr.write("STDIO_SERVER_READY\\n")
    sys.stderr.flush()

    logger.info("Starting MCP server on stdio...")
    # Use run_stdio_async - this handles the reading/writing loop.
    await mcp_server.run_stdio_async() # This blocks until stdin closes or error
    logger.info("Stdio server finished.")

if __name__ == "__main__":
    # Determine transport based on args or environment
    transport_mode = "stdio" # Example: could be set via args

    logger.info(f"Starting main function (mode: {transport_mode})")
    try:
        if transport_mode == "sse":
            # asyncio.run(start_server(...)) # Call SSE version
            pass
        else: # Default to stdio
            asyncio.run(start_stdio_server())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.error(f"Unhandled exception in top-level: {e}", exc_info=True)
        sys.exit(1)
```

**Running the Stdio Server:** The client process typically starts the server script as a subprocess.

---

## 5. Creating an MCP Client

The client connects to the server and calls its tools.

```python
# Example: src/my_mcp_client.py
import asyncio
import logging
import sys
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client # For SSE
from mcp.client.stdio import stdio_client, StdioServerParameters # For Stdio

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("MyMCPClient")

async def run_sse_client(server_url: str):
    """Connects to an SSE server and calls the echo tool."""
    sse_endpoint_url = f"{server_url}/sse" # IMPORTANT: Target the /sse endpoint
    logger.info(f"Connecting to SSE endpoint: {sse_endpoint_url}")

    try:
        # Use async with for the transport client
        async with sse_client(sse_endpoint_url) as streams:
            read_stream, write_stream = streams
            logger.info(f"SSE streams obtained for {sse_endpoint_url}")

            # Use async with for the ClientSession
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("MCP ClientSession created")

                # **CRITICAL: Initialize the session with a timeout.**
                logger.info("Initializing MCP session...")
                try:
                    await asyncio.wait_for(session.initialize(), timeout=15.0)
                    logger.info("MCP session initialized successfully")
                except asyncio.TimeoutError:
                    logger.error("Timeout initializing MCP session.")
                    return
                except Exception as init_err:
                    logger.error(f"Error initializing MCP session: {init_err}", exc_info=True)
                    return

                # Optional brief sleep if encountering timing issues *after* successful init
                # await asyncio.sleep(0.1)

                # Call the tool
                tool_name = "echo"
                params = {"message": "Hello from SSE Client!"}
                logger.info(f"Calling tool '{tool_name}' with params: {params}")
                try:
                    result = await asyncio.wait_for(
                        session.call_tool(tool_name, params),
                        timeout=15.0
                    )
                    logger.info(f"Received result: {result}")

                    # Process result
                    if result and not result.isError and result.content:
                        # Expecting TextContent with JSON string
                        if isinstance(result.content[0], TextContent):
                            response_text = result.content[0].text
                            logger.info(f"Tool response text: {response_text!r}")
                            # Further parsing/validation...
                            # response_data = json.loads(response_text)
                            # assert response_data.get("echoed") == params["message"]
                        else:
                            logger.warning(f"Unexpected content type: {type(result.content[0])}")
                    elif result and result.isError:
                        logger.error(f"Tool call failed: {result.content}")
                    else:
                        logger.error("Tool call returned None or unexpected structure.")

                except asyncio.TimeoutError:
                    logger.error(f"Timeout calling tool '{tool_name}'.")
                except Exception as call_err:
                    logger.error(f"Error calling tool '{tool_name}': {call_err}", exc_info=True)

    except ConnectionRefusedError:
        logger.error(f"Connection refused when connecting to {sse_endpoint_url}. Is the server running?")
    except Exception as conn_err:
        logger.error(f"Error during SSE client connection: {conn_err}", exc_info=True)


async def run_stdio_client(server_script_path: str):
    """Starts a stdio server subprocess, connects, and calls the echo tool."""
    logger.info(f"Preparing to start stdio server: {server_script_path}")
    server_params = StdioServerParameters(
        command=[sys.executable, server_script_path] # Command to start the server
    )

    try:
        # Use async with for the stdio_client
        async with stdio_client(server_params) as streams:
            read_stream, write_stream = streams
            logger.info("Stdio streams obtained.")

            # Use async with for the ClientSession
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("MCP ClientSession created")

                # **CRITICAL: Initialize the session with a timeout.**
                logger.info("Initializing MCP session...")
                try:
                    await asyncio.wait_for(session.initialize(), timeout=15.0)
                    logger.info("MCP session initialized successfully")
                except asyncio.TimeoutError:
                    logger.error("Timeout initializing MCP session.")
                    return
                except Exception as init_err:
                    logger.error(f"Error initializing MCP session: {init_err}", exc_info=True)
                    return

                # Call the tool
                tool_name = "echo"
                params = {"message": "Hello from Stdio Client!"}
                logger.info(f"Calling tool '{tool_name}' with params: {params}")
                try:
                    result = await asyncio.wait_for(
                        session.call_tool(tool_name, params),
                        timeout=15.0
                    )
                    logger.info(f"Received result: {result}")
                    # Process result (similar to SSE example)...

                except asyncio.TimeoutError:
                    logger.error(f"Timeout calling tool '{tool_name}'.")
                except Exception as call_err:
                    logger.error(f"Error calling tool '{tool_name}': {call_err}", exc_info=True)

    except Exception as conn_err:
        logger.error(f"Error during stdio client connection: {conn_err}", exc_info=True)


if __name__ == "__main__":
    # Example Usage
    # asyncio.run(run_sse_client("http://127.0.0.1:8765"))
    # asyncio.run(run_stdio_client("src/my_mcp_server.py")) # Assuming server script handles stdio
    pass

```

**Key Points for Clients (v1.6):**
*   **Use `async with`:** Manage transport clients (`sse_client`, `stdio_client`) and `ClientSession` with `async with` to ensure proper resource cleanup.
*   **Initialize Session:** ALWAYS `await session.initialize()` immediately after creating the `ClientSession`, preferably within an `asyncio.wait_for` block.
*   **SSE Endpoint:** Connect specifically to the `/sse` endpoint of your server (e.g., `http://host:port/sse`).
*   **Timeouts:** Use `asyncio.wait_for` around `initialize()` and `call_tool()` to prevent hangs.

---

## 6. Integration Testing Strategy

Reliable integration testing is crucial. OpenMAS uses a test harness approach.

### 6.1. The `McpTestHarness` Utility

Found in `tests/integration/mcp/test_utils.py`, this class provides a standardized way to:
1.  **Start Server:** Launch the server script (stdio or SSE) as a subprocess.
2.  **Verify Startup:**
    *   Read `stderr` from the subprocess.
    *   Wait for a readiness signal (`STDIO_SERVER_READY` or `SSE_SERVER_URL=...`).
    *   **(SSE Only)** Perform an HTTP GET check (using `aiohttp`) against the `/sse` endpoint to confirm Uvicorn/FastAPI is truly listening and the route is available. This uses a retry loop and handles transient connection errors during startup.
3.  **Provide Connection Info:** Stores the `server_url` (for SSE).
4.  **Cleanup:** Terminates/kills the server subprocess reliably.

### 6.2. Test Structure Example (SSE)

```python
# From: tests/integration/mcp/test_sse_tool_calls.py

# Imports: asyncio, json, logging, pytest, mcp types, harness, etc.
# Skip tests if aiohttp/mcp not available...

@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_AIOHTTP, reason=SKIP_REASON)
async def test_sse_echo_basic_types() -> None:
    test_port = 8765 + random.randint(0, 1000) # Use random port
    logger.info(f"Using test port: {test_port}")
    harness = McpTestHarness(TransportType.SSE, test_port=test_port)

    try:
        # Start server subprocess using the harness
        logger.info("Starting server subprocess")
        # Pass port via additional_args to the script
        process = await harness.start_server(
            additional_args=["--host", "127.0.0.1", "--port", str(test_port)]
        )
        # Basic check if process started immediately
        if process.returncode is not None:
            # Read/log stderr if available...
            pytest.fail(f"Process failed to start with return code {process.returncode}")
            return

        logger.info("Server process started, waiting for readiness signal & HTTP check...")
        # Harness waits for stderr signal AND performs HTTP check
        startup_ok = await harness.verify_server_startup(timeout=15.0)
        assert startup_ok, "Server startup verification failed (check harness logs)"
        assert harness.server_url, "Server URL not found via harness"
        logger.info(f"Server ready, URL: {harness.server_url}")

        # Construct the /sse endpoint URL from the harness
        sse_endpoint_url = f"{harness.server_url}/sse"
        logger.info(f"Connecting to SSE endpoint: {sse_endpoint_url}")

        # Client connection logic (as shown in Section 5)
        async with sse_client(sse_endpoint_url) as streams:
            read_stream, write_stream = streams
            logger.info("SSE client streams obtained")
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("MCP ClientSession created")
                # Initialize
                await asyncio.wait_for(session.initialize(), timeout=15.0)
                logger.info("MCP session initialized")
                # Call tool
                result = await asyncio.wait_for(
                    session.call_tool("echo", {"message": "Hello, MCP!"}),
                    timeout=15.0
                )
                logger.info(f"Echo result: {result}")
                # Assertions
                assert result is not None
                assert not result.isError
                assert result.content and isinstance(result.content[0], TextContent)
                response_data = json.loads(result.content[0].text)
                assert response_data.get("echoed") == "Hello, MCP!"
                logger.info("Echo test passed")

    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        # Harness ensures subprocess cleanup
        logger.info("Cleaning up test harness...")
        await harness.cleanup()
        logger.info("Test harness cleaned up.")

```
*(See `test_stdio_tool_calls.py` for the stdio equivalent using the harness).*

### 6.3. Running Tests

Use `tox` as configured in the project (`tox.ini`) to ensure tests run in isolated environments with the correct dependencies.

```bash
# Run all MCP integration tests for python 3.10
tox -e py310-mcp

# Run a specific MCP test file
tox -e py310-mcp -- tests/integration/mcp/test_sse_tool_calls.py

# Run a specific MCP test function
tox -e py310-mcp -- tests/integration/mcp/test_sse_tool_calls.py::test_sse_echo_basic_types
```
*(Remember to use the correct path relative to the project root when specifying tests for tox).*

---

## 7. Debugging

*   **Logging:** Enable `DEBUG` level logging in your server script (`FastMCP(log_level="DEBUG")`, `logging.basicConfig(level=logging.DEBUG, ...)`), client script, and test harness. Examine server `stderr` carefully.
*   **MCP Inspector:** Use the command-line inspector for local debugging (requires `mcp[cli]`):
    ```bash
    # Run your server script first (e.g., python src/my_mcp_server.py)

    # Then run the inspector, connecting to your running server
    mcp dev --sse-url http://localhost:8765/sse # For SSE
    # or
    # mcp dev --stdio-command "python src/my_mcp_server.py" # For stdio
    ```
    This provides a web UI (usually `http://localhost:5173`) to list and call tools manually.
*   **Isolate:** Create minimal server/client examples outside the test harness to verify basic functionality.
*   **Check Readiness Signal:** Ensure the server script prints the *exact* readiness signal (`STDIO_SERVER_READY` or `SSE_SERVER_URL=...`) to `stderr` *before* starting the blocking server loop (`run_stdio_async` or `serve`).
*   **Check HTTP Verification (SSE):** Look at the `McpTestHarness` logs during `verify_server_startup`. If the HTTP check to `/sse` fails repeatedly (e.g., 500, 404, timeout), there's likely an issue with the FastAPI/Uvicorn setup in the server script.

---

## 8. Known Issues & Gotchas (MCP v1.6)

*   **SSE Server Setup Complexity:** Running `FastMCP` with SSE requires manual integration with FastAPI/Uvicorn as detailed in Section 4.1. Simply passing `FastMCP` as the app to Uvicorn or using `FastMCP.run(transport='sse')` **does not work reliably** and often leads to 500 errors or event loop issues.
*   **Missing `/messages` Mount (SSE):** Forgetting to mount the `sse_transport.handle_post_message` route in the FastAPI app (Section 4.1, Step 4) will cause client-side timeouts or errors during `session.initialize()` or `session.call_tool()` because the client cannot POST messages back to the server. Look for 404 errors related to `/messages/` in client logs.
*   **Tool Return Values:** Returning manually constructed `CallToolResult` or `TextContent` objects from tools can lead to double-encoding or validation errors (Section 3.2). Return simple JSON strings for success, raise exceptions for errors.
*   **`session.initialize()`:** Must be called explicitly and awaited after creating `ClientSession` (Section 5). Omitting it leads to errors.
*   **SSE Endpoint:** Clients must connect to the specific `/sse` path, not the root URL (Section 5).
*   **Stdio Logging:** Server logs *must* go to `stderr`. Any output to `stdout` other than MCP JSON messages will break communication.

---

## 9. Advanced Topics & Lessons from Integration Testing

### 9.1 Managing Concurrent Connections

When deploying an MCP server in a multi-agent system, you must ensure it can handle multiple client connections simultaneously. Our integration tests revealed several important considerations:

#### 9.1.1. Server-Side Considerations for Concurrent Clients

* **Statelessness:** Keep tool implementations stateless or use proper locking mechanisms. Tools may be called by different clients concurrently.
* **Resource Management:** Monitor and limit resource usage (memory, file handles, database connections) as each client connection consumes resources.
* **Connection Limits:** Consider implementing connection limits if your server might be overwhelmed by too many simultaneous clients.
* **Per-Client Tracking:** In complex scenarios, you might need to track client state (e.g., using client identifiers from the connection context).

#### 9.1.2. Best Practices for SSE Transport with Concurrent Clients

```python
# In FastAPI setup for MCP server:

# Configure FastAPI with proper concurrency settings
app = FastAPI(
    title="MCP Server with Concurrency Support",
    version="1.0"
)

# Configure Uvicorn with appropriate worker settings
config = uvicorn.Config(
    app=app,
    host=host,
    port=port,
    log_level="info",
    # Consider these settings for production:
    workers=4,     # Multiple workers for concurrent load
    limit_concurrency=100,  # Max concurrent connections
)
```

#### 9.1.3. Client-Side Concurrency Considerations

* **Connection Pooling:** For clients making multiple connections, consider implementing connection pooling.
* **Timeouts:** Always use timeouts with `asyncio.wait_for()` for client operations to prevent hanging.
* **Retry Logic:** Implement exponential backoff retry logic for transient connection issues.

### 9.2 Connection Resilience

Our integration tests demonstrated that proper handling of abrupt client disconnections is essential for robust MCP servers. The following patterns help ensure your server remains stable:

#### 9.2.1. Handling Client Disconnections

* **Proper Exception Handling:** The server must catch and log exceptions from broken connections without crashing.
* **Resource Cleanup:** Ensure all resources (streams, sessions, file handles) are properly cleaned up when a client disconnects.
* **Graceful Degradation:** The server should continue operating for other clients even if one client disconnects unexpectedly.

```python
# Example: Robust SSE endpoint handling in FastAPI
@app.get("/sse", tags=["MCP"])
async def handle_sse_connection(request: Request):
    """
    Handles incoming SSE connection requests with robust error handling.
    """
    client_id = request.client.host if request.client else "unknown"
    logger.info(f"Incoming SSE connection request from {client_id}")
    try:
        async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (
            read_stream,
            write_stream,
        ):
            logger.info(f"SSE connection established for {client_id}")
            try:
                await mcp_server._mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server._mcp_server.create_initialization_options(),
                )
                logger.info(f"MCP server loop completed normally for {client_id}")
            except asyncio.CancelledError:
                logger.info(f"Connection cancelled for {client_id}")
                raise
            except Exception as run_err:
                logger.error(f"Error in MCP server loop for {client_id}: {run_err}", exc_info=True)
                # Don't re-raise - let this client's connection terminate but keep server running
    except asyncio.CancelledError:
        logger.info(f"SSE connection setup cancelled for {client_id}")
        raise
    except Exception as e:
        logger.error(f"Error during SSE connection setup for {client_id}: {e}", exc_info=True)
        # Return appropriate HTTP error if response hasn't been sent yet
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error during connection setup"}
        )
```

#### 9.2.2. Client-Side Connection Management

* **Context Managers:** Always use `async with` context managers for both transport clients and `ClientSession` to ensure proper cleanup.
* **Explicit Initialization:** Always call and await `session.initialize()` after creating a `ClientSession`.
* **Proper Shutdown:** Let context managers handle the cleanup; avoid manually calling `__aenter__` or `__aexit__` methods.

```python
# Recommended pattern for robust client connections
async def connect_to_mcp_server(server_url: str):
    """Connects to an MCP server with proper error handling."""
    sse_endpoint_url = f"{server_url}/sse"
    logger.info(f"Connecting to MCP server at {sse_endpoint_url}")

    try:
        # Use async with to ensure proper cleanup even if exceptions occur
        async with sse_client(sse_endpoint_url) as streams:
            read_stream, write_stream = streams
            logger.info("SSE streams established")

            async with ClientSession(read_stream, write_stream) as session:
                logger.info("MCP session created")

                # Always initialize with a timeout
                await asyncio.wait_for(session.initialize(), timeout=10.0)
                logger.info("MCP session initialized")

                # Now the session is ready to use
                result = await asyncio.wait_for(
                    session.call_tool("echo", {"message": "Test message"}),
                    timeout=5.0
                )

                # Process result...

    except asyncio.TimeoutError:
        logger.error("Timeout connecting to MCP server")
    except asyncio.CancelledError:
        logger.info("Connection attempt cancelled")
        raise
    except Exception as e:
        logger.error(f"Error connecting to MCP server: {e}", exc_info=True)
```

### 9.3 Testing Connection Resilience

Our integration tests for connection resilience reveal important testing patterns:

#### 9.3.1. Testing Normal Disconnections

Verify that the server properly handles clients that disconnect cleanly by using context managers:

```python
async with sse_client(endpoint_url) as streams:
    async with ClientSession(*streams) as session:
        await session.initialize()
        # Make test calls...
# Connection will be closed properly when exiting context managers
```

#### 9.3.2. Testing Abrupt Disconnections

For testing abrupt disconnections, use a task cancellation approach rather than manually closing streams:

```python
async def client_task():
    async with sse_client(endpoint_url) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            await session.call_tool("echo", {"message": "test"})
            # Wait indefinitely (will be cancelled)
            await asyncio.Event().wait()

# Start client in a separate task
client = asyncio.create_task(client_task())

# Wait for client to connect and make initial call
await asyncio.sleep(1.0)

# Simulate crash by cancelling the task
client.cancel()
await asyncio.gather(client, return_exceptions=True)

# Test that server is still operational by connecting a new client
async with sse_client(endpoint_url) as streams:
    # ...and so on
```

#### 9.3.3. Testing Concurrent Clients

When testing multiple concurrent clients, use `asyncio.gather()` to run them simultaneously:

```python
async def run_client(client_id):
    async with sse_client(endpoint_url) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            result = await session.call_tool("echo", {"message": f"client {client_id}"})
            return client_id, result

# Start multiple clients concurrently
clients = [run_client(i) for i in range(10)]
results = await asyncio.gather(*clients, return_exceptions=True)

# Verify all clients succeeded
for client_id, result in results:
    assert not result.isError, f"Client {client_id} failed"
```

### 9.4 Resource Management & Cleanup

Our testing revealed several key considerations for proper resource management:

#### 9.4.1. Server-Side Resource Management

* **Connection Tracking:** Consider implementing a mechanism to track active connections and their resource usage.
* **Timeouts:** Add timeouts to all I/O operations to prevent resource exhaustion from stalled connections.
* **Graceful Shutdown:** Implement a graceful shutdown mechanism that waits for active operations to complete but has a timeout.

#### 9.4.2. Timeout Patterns

Always use timeouts with I/O operations, especially in servers handling multiple clients:

```python
# Server-side timeout example
@app.get("/sse", tags=["MCP"])
async def handle_sse_connection(request: Request):
    # Use a server-side timeout for the entire connection lifetime
    connection_timeout = 3600  # 1 hour max per connection
    try:
        async with sse_transport.connect_sse(...) as streams:
            # Run with timeout
            await asyncio.wait_for(
                mcp_server._mcp_server.run(*streams, mcp_server._mcp_server.create_initialization_options()),
                timeout=connection_timeout
            )
    except asyncio.TimeoutError:
        logger.warning(f"Connection timed out after {connection_timeout}s")
    except Exception as e:
        logger.error(f"Error during connection: {e}")
```

#### 9.4.3. Cleanup During Test Harness Shutdown

When writing integration tests, ensure proper cleanup with timeouts to avoid hanging tests:

```python
# Clean up test resources with timeout
try:
    cleanup_task = asyncio.create_task(harness.cleanup())
    await asyncio.wait_for(cleanup_task, timeout=5.0)
    logger.info("Test harness cleaned up")
except asyncio.TimeoutError:
    logger.warning("Cleanup timed out - resources may still be active")
    # Force terminate if needed
    if harness.process and harness.process.returncode is None:
        harness.process.kill()
```

---
