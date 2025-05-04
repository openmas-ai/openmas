# MCP SSE Tool Call Tutorial

This tutorial walks through implementing MCP tool calls using Server-Sent Events (SSE) transport in OpenMAS. The SSE transport allows for network-based communication between agents, enabling more flexible deployment scenarios than stdio-based communication.

## Prerequisites

Before you begin, make sure you have:

1. OpenMAS installed
2. Python 3.10 or later
3. Dependencies: `mcp>=1.6.0,<1.7.0`, `aiohttp`, `httpx`
4. A basic understanding of MCP concepts (see the [MCP Developer Guide](mcp_developer_guide.md))
5. An available HTTP port (this tutorial uses 8000)

## Overview

We'll create a simple example with two agents:

1. **Tool Provider Agent**: Starts an HTTP server with an SSE endpoint that exposes the `process_data` tool
2. **Tool User Agent**: Connects to the provider via HTTP and calls the tool to process text data

## Project Structure

The full example is available in the repository at `examples/example_02_mcp/01_mcp_sse_tool_call/`.

```
01_mcp_sse_tool_call/
├── agents/
│   ├── tool_provider/
│   │   ├── __init__.py
│   │   └── agent.py
│   ├── tool_user/
│   │   ├── __init__.py
│   │   └── agent.py
│   └── __init__.py
├── openmas_project.yml
├── README.md
└── test_example.py
```

## Step 1: Create the Project Configuration

First, create an `openmas_project.yml` file with the following configuration:

```yaml
name: example_02_mcp_sse_tool_call
version: 0.1.0
description: "Example demonstrating MCP tool calls over Server-Sent Events (SSE)"

# Define the available agents
agents:
  tool_provider: "agents/tool_provider"
  tool_user: "agents/tool_user"

# Default configuration for all agents
default_config:
  log_level: INFO

# Default communicator settings
communicator_defaults:
  type: mcp-sse
  options:
    server_mode: false

# Agent-specific configurations
agent_configs:
  # Tool provider config - run in server mode to expose tools via HTTP
  tool_provider:
    communicator_options:
      server_mode: true
      server_instructions: "A service that processes text using an MCP tool"
      host: "127.0.0.1"
      port: 8000

  # Tool user config - client mode with service URLs to connect to the provider
  tool_user:
    service_urls:
      tool_provider: "http://127.0.0.1:8000"
```

Key points:
- We set the communicator type to `mcp-sse` instead of `mcp-stdio`
- The tool provider runs in server mode on port 8000
- The tool user connects via HTTP URL instead of stdio command

## Step 2: Implement the Tool Provider Agent

Create the tool provider agent in `agents/tool_provider/agent.py`:

```python
"""Tool provider agent that registers and exposes an MCP tool via SSE."""

import asyncio
import signal
from typing import Any, Dict

from openmas.agent import BaseAgent
from openmas.logging import get_logger

logger = get_logger(__name__)


class ToolProviderAgent(BaseAgent):
    """Agent that provides an MCP tool over SSE.

    This agent registers a tool called "process_data" that handles
    incoming data and returns a processed result.

    Unlike stdio-based tools, this provider runs as an HTTP server that
    clients can connect to via SSE. The server will continue running
    until explicitly shut down.
    """

    async def setup(self) -> None:
        """Set up the agent by registering the MCP tool."""
        logger.info("Setting up ToolProviderAgent")

        # Register signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._handle_signal(s)))

        # Try to register as an MCP tool
        tool_name = "process_data"

        try:
            # If using a real MCP communicator, register as a tool
            if hasattr(self.communicator, "register_tool"):
                await self.communicator.register_tool(
                    name=tool_name,
                    description="Process incoming data and return a result",
                    function=self.process_data_handler,
                )
                logger.info(f"Registered MCP tool: {tool_name}")
            else:
                await self.communicator.register_handler(f"tool/call/{tool_name}", self.process_data_handler)
                logger.info(f"Registered handler for tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error registering tool/handler: {e}")
            raise

        # Get server details if available
        if hasattr(self.communicator, "get_server_info"):
            server_info = await self.communicator.get_server_info()
            if server_info:
                logger.info(f"SSE Server running at: {server_info.get('url', 'unknown')}")

        logger.info("ToolProviderAgent setup complete")

    async def process_data_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming tool calls by processing the provided data.

        Args:
            payload: Dictionary containing the data to process

        Returns:
            Dictionary containing the processed result
        """
        logger.info(f"Tool handler received data: {payload}")

        # Simple data processing - in a real-world scenario, this might involve
        # complex transformations, model inference, or other operations
        if "text" in payload:
            processed_text = payload["text"].upper()
            word_count = len(payload["text"].split())

            result = {"processed_text": processed_text, "word_count": word_count, "status": "success"}
        else:
            result = {"error": "No text field in payload", "status": "error"}

        logger.info(f"Tool handler returning result: {result}")
        return result

    async def run(self) -> None:
        """Run the agent.

        For SSE server, we need to keep the agent alive while the server is running.
        This method will block indefinitely until the server is shut down.
        """
        logger.info("ToolProviderAgent running, waiting for tool calls via SSE")

        # For a real MCP communicator with SSE, we need to keep the server running
        if hasattr(self.communicator, "register_tool"):
            # Create an event to signal shutdown
            self._shutdown_event = asyncio.Event()

            # Wait for the shutdown signal
            try:
                await self._shutdown_event.wait()
                logger.info("Shutdown event received, preparing to stop")
            except asyncio.CancelledError:
                logger.info("Run method cancelled, preparing to stop")
        else:
            # For testing with mock communicator, just return immediately
            logger.info("ToolProviderAgent run complete (test mode)")

    async def _handle_signal(self, sig: signal.Signals) -> None:
        """Handle termination signals for graceful shutdown.

        Args:
            sig: The signal received
        """
        logger.info(f"Received signal {sig.name}, initiating shutdown")
        if hasattr(self, "_shutdown_event"):
            self._shutdown_event.set()

    async def shutdown(self) -> None:
        """Shut down the agent.

        For SSE servers, we need to properly stop the HTTP server.
        """
        logger.info("ToolProviderAgent shutting down")

        # If using a real MCP communicator with a server, properly shut down the server
        if hasattr(self.communicator, "stop_server"):
            logger.info("Stopping SSE server")
            try:
                await self.communicator.stop_server()
                logger.info("SSE server stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping SSE server: {e}")

        # Set the shutdown event if it exists
        if hasattr(self, "_shutdown_event"):
            self._shutdown_event.set()
```

Don't forget to create `agents/tool_provider/__init__.py`:

```python
"""Tool provider agent for MCP SSE."""

from .agent import ToolProviderAgent
```

## Step 3: Implement the Tool User Agent

Create the tool user agent in `agents/tool_user/agent.py`:

```python
"""Tool user agent that calls an MCP tool via SSE."""

import asyncio
from typing import Any, Dict, Optional

from openmas.agent import BaseAgent
from openmas.logging import get_logger

logger = get_logger(__name__)


class ToolUserAgent(BaseAgent):
    """Agent that uses an MCP tool over SSE.

    This agent calls the "process_data" tool provided by the ToolProviderAgent,
    sends some text data, and processes the result.

    Unlike stdio-based tools, this agent connects to the provider over HTTP
    using Server-Sent Events (SSE).
    """

    async def setup(self) -> None:
        """Set up the agent."""
        logger.info("Setting up ToolUserAgent")
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[Dict[str, str]] = None

        # Verify that the service URL for the tool provider is properly configured
        if hasattr(self.communicator, "service_urls") and "tool_provider" in self.communicator.service_urls:
            url = self.communicator.service_urls["tool_provider"]
            logger.info(f"Tool provider service URL configured: {url}")
        else:
            logger.warning("No tool provider service URL configured")

        logger.info("ToolUserAgent setup complete")

    async def run(self) -> None:
        """Run the agent by calling the process_data tool."""
        logger.info("ToolUserAgent running, calling process_data tool")

        # Prepare the data to send to the tool
        tool_payload = {"text": "Hello, this is a sample text that needs processing."}
        tool_name = "process_data"

        try:
            # Try to use MCP call_tool if available, otherwise use send_request
            logger.info(f"Calling tool '{tool_name}' with payload: {tool_payload}")

            # Set a timeout for the tool call to prevent hanging
            # For network-based SSE communication, we might need a longer timeout
            # than for stdio-based communication
            timeout_seconds = 15.0

            if hasattr(self.communicator, "call_tool"):
                # Call the process_data tool using MCP call_tool with timeout
                result = await self._call_tool_with_timeout(
                    target_service="tool_provider", tool_name=tool_name, arguments=tool_payload, timeout=timeout_seconds
                )
            else:
                # For testing with MockCommunicator, use send_request with the tool/call/ prefix
                result = await self._send_request_with_timeout(
                    target_service="tool_provider",
                    method=f"tool/call/{tool_name}",
                    params=tool_payload,
                    timeout=timeout_seconds,
                )

            # Store the result for verification in tests
            self.result = result

            # Log the result
            logger.info(f"Received tool result: {result}")

            if result.get("status") == "success":
                logger.info(f"Successfully processed text. Word count: {result.get('word_count')}")
                logger.info(f"Processed text: {result.get('processed_text')}")
            else:
                logger.error(f"Tool call failed: {result.get('error')}")

        except asyncio.TimeoutError:
            error_msg = f"Tool call to '{tool_name}' timed out after {timeout_seconds} seconds"
            logger.error(error_msg)
            self.error = {"error": error_msg, "status": "timeout"}
        except ConnectionError as ce:
            error_msg = f"Connection error calling tool '{tool_name}': {ce}"
            logger.error(error_msg)
            self.error = {"error": error_msg, "status": "connection_error"}
        except Exception as e:
            error_msg = f"Error calling tool: {e}"
            logger.error(error_msg)
            self.error = {"error": str(e), "status": "error"}

        logger.info("ToolUserAgent completed its run method")

    async def _call_tool_with_timeout(
        self, target_service: str, tool_name: str, arguments: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        """Call a tool with a timeout to prevent hanging.

        Args:
            target_service: The name of the service providing the tool
            tool_name: The name of the tool to call
            arguments: The arguments to pass to the tool
            timeout: Timeout in seconds

        Returns:
            The result of the tool call

        Raises:
            asyncio.TimeoutError: If the call times out
            ConnectionError: If connection to the provider fails
        """
        # For SSE, the initial connection might take some time, especially
        # if the server is still starting up
        connection_attempts = 3
        backoff_seconds = 1.0

        # Try multiple times with exponential backoff
        for attempt in range(1, connection_attempts + 1):
            try:
                logger.info(f"Tool call attempt {attempt}/{connection_attempts}")
                return await asyncio.wait_for(
                    self.communicator.call_tool(target_service=target_service, tool_name=tool_name, arguments=arguments),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                if attempt < connection_attempts:
                    logger.warning(f"Tool call attempt {attempt} timed out, retrying in {backoff_seconds}s")
                    await asyncio.sleep(backoff_seconds)
                    backoff_seconds *= 2  # Exponential backoff
                else:
                    logger.error(f"Tool call failed after {connection_attempts} attempts")
                    raise
            except ConnectionError as ce:
                if attempt < connection_attempts:
                    logger.warning(f"Connection error on attempt {attempt}, retrying in {backoff_seconds}s: {ce}")
                    await asyncio.sleep(backoff_seconds)
                    backoff_seconds *= 2  # Exponential backoff
                else:
                    logger.error(f"Connection failed after {connection_attempts} attempts: {ce}")
                    raise

    async def _send_request_with_timeout(
        self, target_service: str, method: str, params: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        """Send a request with a timeout to prevent hanging.

        Args:
            target_service: The name of the target service
            method: The method to call
            params: The parameters to pass
            timeout: Timeout in seconds

        Returns:
            The response from the service

        Raises:
            asyncio.TimeoutError: If the request times out
        """
        return await asyncio.wait_for(
            self.communicator.send_request(target_service=target_service, method=method, params=params), timeout=timeout
        )

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info("ToolUserAgent shutting down")

        # Close any open connections to the provider
        if hasattr(self.communicator, "close_connections"):
            try:
                await self.communicator.close_connections()
                logger.info("Closed connections to tool provider")
            except Exception as e:
                logger.error(f"Error closing connections: {e}")
```

Don't forget to create `agents/tool_user/__init__.py`:

```python
"""Tool user agent for MCP SSE."""

from .agent import ToolUserAgent
```

Also create `agents/__init__.py`:
```python
"""Agent modules for MCP SSE Tool Call example."""
```

## Step 4: Running the Example

### Method 1: Running Separately

1. First, start the tool provider agent:

```bash
openmas run tool_provider --project examples/example_02_mcp/01_mcp_sse_tool_call
```

2. Then, in another terminal, start the tool user agent:

```bash
openmas run tool_user --project examples/example_02_mcp/01_mcp_sse_tool_call
```

### Method 2: Running the Test Script

The example includes a test script that runs both agents together and verifies the functionality:

```bash
python examples/example_02_mcp/01_mcp_sse_tool_call/test_example.py
```

## How It Works

Here's what happens when you run the example:

1. **Provider Setup**:
   - The tool provider agent starts an HTTP server on port 8000
   - It registers the `process_data` tool
   - The server has an SSE endpoint at `/sse` and a message handling endpoint at `/messages`

2. **User Connection**:
   - The tool user agent connects to the provider's SSE endpoint
   - It initializes an MCP session over the SSE connection
   - It calls the `process_data` tool with a text payload

3. **Data Processing**:
   - The provider receives the tool call
   - It processes the text (converts to uppercase and counts words)
   - It returns the result to the user

4. **Result Handling**:
   - The user receives the result and displays it
   - It verifies the structure and content of the result

## Comparing SSE vs Stdio

| Feature | SSE | Stdio |
|---------|-----|-------|
| Communication | Network-based (HTTP) | Process-based (stdin/stdout) |
| Multiple Clients | ✅ Supports multiple clients | ❌ Only one client per provider |
| Deployment | ✅ Can run on separate machines | ❌ Must run on same machine |
| Setup | More complex (HTTP server) | Simpler (process pipes) |
| Timeout Handling | Needs network timeouts | Process timeouts |
| Connection Resilience | Can reconnect if connection drops | Process must restart |
| Security | Requires network security | Process isolation |

## Common Issues and Troubleshooting

### Connection Issues

- **Provider not starting**: Check if the port is already in use
- **Connection refused**: Ensure the provider is running and the port is accessible
- **Timeout during initialization**: The server might need more time to start

### Port Conflicts

If port 8000 is already in use:

1. Choose a different port in `openmas_project.yml`
2. Update the service URL to match the new port

### Network Restrictions

- Ensure the chosen port is not blocked by a firewall
- For distributed setups, modify the host from `127.0.0.1` to the actual IP or hostname

## Extending the Example

Here are some ways to extend this example:

1. **Add Authentication**: Implement a simple authentication mechanism for the HTTP server
2. **Multiple Tools**: Register additional tools with different functionality
3. **Load Balancing**: Create multiple provider instances behind a load balancer
4. **Connection Pooling**: Implement connection pooling for the client to reuse connections
5. **HTTPS**: Configure the provider to use HTTPS for secure communication

## Next Steps

- Learn about more advanced MCP features in the [MCP Developer Guide](mcp_developer_guide.md)
- Explore other OpenMAS examples and patterns
- Read about [Agent Chaining](../patterns/agent_chaining.md) to combine multiple agents
