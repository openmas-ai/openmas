# MCP SSE Tool Call Tutorial

This tutorial walks through implementing MCP tool calls using Server-Sent Events (SSE) transport in OpenMAS. The SSE transport allows for network-based communication between agents, enabling more flexible deployment scenarios than stdio-based communication.

## Prerequisites

Before you begin, make sure you have:

1. OpenMAS installed
2. Python 3.10 or later
3. Dependencies: `mcp>=1.7.1`, `aiohttp`, `httpx`
4. A basic understanding of MCP concepts (see the [MCP Developer Guide](mcp_developer_guide.md))
5. An available HTTP port (this tutorial uses 8000)

## Overview

We'll create a simple example with two agents:

1. **Tool Provider Agent**: Starts an HTTP server with an SSE endpoint that exposes the `process_text` tool
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
description: "Example demonstrating MCP tool calls over Server-Sent Events (SSE) using MCP 1.7.1"

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
      http_host: "127.0.0.1"
      http_port: 8000

  # Tool user config - client mode with service URLs to connect to the provider
  tool_user:
    service_urls:
      tool_provider: "http://127.0.0.1:8000/sse"
```

Key points:
- The communicator type is `mcp-sse` for Server-Sent Events transport
- The tool provider runs in server mode on port 8000
- The tool user connects via HTTP URL, specifically to the `/sse` endpoint
- Note the `http_host` and `http_port` fields align with MCP 1.7.1 naming conventions

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

    This agent registers a tool called "process_text" that handles
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

        # Register the MCP tool
        tool_name = "process_text"

        try:
            await self.communicator.register_tool(
                name=tool_name,
                description="Process incoming text and return the result",
                function=self.process_text_handler,
            )
            logger.info(f"Registered MCP tool: {tool_name}")

            # Get server details if available
            if hasattr(self.communicator, "get_server_info"):
                server_info = await self.communicator.get_server_info()
                if server_info:
                    logger.info(f"SSE Server running at: {server_info.get('url', 'unknown')}")

        except Exception as e:
            logger.error(f"Error registering tool: {e}")
            raise

        logger.info("ToolProviderAgent setup complete")

    async def process_text_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming tool calls by processing the provided text.

        Args:
            payload: Dictionary containing the text to process

        Returns:
            Dictionary containing the processed result
        """
        logger.info(f"Tool handler received payload: {payload}")

        # MCP 1.7.1 can send arguments in different ways, so check both formats
        text = None

        # Check for direct text field
        if "text" in payload:
            text = payload["text"]
            logger.info("Found text in direct text field")

        # Check for content array format (MCP 1.7.1 style)
        elif "content" in payload and isinstance(payload["content"], list) and len(payload["content"]) > 0:
            content_item = payload["content"][0]
            if isinstance(content_item, dict) and "text" in content_item:
                text = content_item["text"]
                logger.info("Found text in content[0].text")
            elif hasattr(content_item, "text"):
                # Handle MCP TextContent object
                text = content_item.text
                logger.info("Found text in content[0].text object")

        # Process the text if found
        if text is None:
            result = {"error": "No text field found in payload", "status": "error"}
            logger.error(f"Missing text field in payload: {payload}")
        else:
            # Simple processing - convert to uppercase and count words
            processed_text = text.upper()
            word_count = len(text.split())
            result = {"processed_text": processed_text, "word_count": word_count, "status": "success"}

        logger.info(f"Tool handler returning result: {result}")
        return result

    async def run(self) -> None:
        """Run the agent.

        For SSE server, we need to keep the agent alive while the server is running.
        This method will block indefinitely until the server is shut down.
        """
        logger.info("ToolProviderAgent running, waiting for tool calls via SSE")

        # Create an event to signal shutdown
        self._shutdown_event = asyncio.Event()

        # Wait for the shutdown signal
        try:
            await self._shutdown_event.wait()
            logger.info("Shutdown event received, preparing to stop")
        except asyncio.CancelledError:
            logger.info("Run method cancelled, preparing to stop")

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
from openmas.exceptions import CommunicationError

logger = get_logger(__name__)


class ToolUserAgent(BaseAgent):
    """Agent that uses an MCP tool over SSE.

    This agent calls the "process_text" tool provided by the ToolProviderAgent,
    sends text data, and processes the result.
    """

    async def setup(self) -> None:
        """Set up the agent."""
        logger.info("Setting up ToolUserAgent")
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[Dict[str, str]] = None
        logger.info("ToolUserAgent setup complete")

    async def run(self) -> None:
        """Run the agent by calling the process_text tool."""
        logger.info("ToolUserAgent running, calling process_text tool")

        # Prepare the text to process
        test_text = "Hello, this is a sample text that needs processing."

        try:
            # Call the process_text tool with timeout protection
            result = await self._call_process_text(test_text)

            # Store the result for verification
            self.result = result

            # Log the result
            logger.info(f"Process text tool result: {result}")

            if result.get("status") == "success":
                logger.info(f"Successfully processed text: {result.get('processed_text')}")
                logger.info(f"Word count: {result.get('word_count')}")
            else:
                logger.error(f"Tool call failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error during tool call: {e}")
            self.error = {"error": str(e), "status": "error"}

        logger.info("ToolUserAgent completed its run method")

    async def _call_process_text(self, text: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Call the process_text tool with timeout protection.

        Args:
            text: The text to process
            timeout: Timeout in seconds

        Returns:
            The result from the tool

        Raises:
            CommunicationError: If there's an error calling the tool
            asyncio.TimeoutError: If the call times out
        """
        logger.info(f"Calling process_text tool with text: {text}")

        # Create a payload that works with MCP 1.7.1
        # Include both direct text field and content array format
        payload = {
            "text": text,
            # Add content array for MCP 1.7.1 compatibility
            "content": [{"type": "text", "text": text}]
        }

        try:
            # Call the tool with timeout protection
            result = await asyncio.wait_for(
                self.communicator.call_tool(
                    target_service="tool_provider",
                    tool_name="process_text",
                    arguments=payload,
                ),
                timeout=timeout,
            )

            logger.info(f"Received raw result: {result}")
            return result

        except asyncio.TimeoutError:
            error_msg = f"Tool call timed out after {timeout} seconds"
            logger.error(error_msg)
            raise
        except Exception as e:
            error_msg = f"Error calling process_text tool: {e}"
            logger.error(error_msg)
            raise CommunicationError(error_msg)

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info("ToolUserAgent shutting down")
```

Don't forget to create `agents/tool_user/__init__.py`:

```python
"""Tool user agent for MCP SSE."""

from .agent import ToolUserAgent
```

## Step 4: Create a Test Script

Create a test script `test_example.py` to verify that the example works:

```python
"""Test script for the MCP SSE tool call example."""

import asyncio
import logging
import sys
from typing import Dict, Any

from openmas.agent_factory import AgentFactory
from openmas.logging import configure_logging

# Configure logging
configure_logging(logging.INFO)
logger = logging.getLogger(__name__)


async def run_test():
    """Run the test."""
    logger.info("Starting MCP SSE tool call test")

    # Create the agent factory
    factory = AgentFactory()

    # Create the agents
    tool_provider = await factory.create_agent("tool_provider")
    tool_user = await factory.create_agent("tool_user")

    try:
        # Start the provider first
        await tool_provider.start()
        logger.info("Tool provider agent started")

        # Give the server a moment to initialize
        await asyncio.sleep(1.0)

        # Start the user agent
        await tool_user.start()
        logger.info("Tool user agent started")

        # Wait for the user to complete its task
        await asyncio.sleep(2.0)

        # Verify the result
        result = getattr(tool_user, "result", None)
        error = getattr(tool_user, "error", None)

        if result:
            logger.info(f"Test result: {result}")
            assert result.get("status") == "success", "Tool call failed"
            assert "processed_text" in result, "Missing processed_text in result"
            assert "word_count" in result, "Missing word_count in result"
            logger.info("Test passed! Tool call was successful.")
        elif error:
            logger.error(f"Test failed with error: {error}")
            sys.exit(1)
        else:
            logger.error("Test failed - no result or error found")
            sys.exit(1)

    finally:
        # Always clean up the agents
        logger.info("Cleaning up agents")
        await tool_user.stop()
        await tool_provider.stop()
        logger.info("Agents stopped")


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Error running test: {e}", exc_info=True)
        sys.exit(1)
```

## Step 5: Run the Example

Run the example using the following command:

```bash
python test_example.py
```

You should see output showing:
1. The tool provider starting with the MCP SSE server
2. The tool user connecting to the server
3. A successful tool call being made
4. The result being processed

## Key Concepts

### MCP SSE Communicator

The `McpSseCommunicator` in OpenMAS handles all the complexities of setting up an MCP server with SSE transport. When configured with `server_mode=True`, it:

1. Creates an HTTP server using FastAPI and Uvicorn
2. Sets up the MCP FastMCP instance
3. Configures the SSE endpoint
4. Handles tool registration

### Tool Registration and Handling

Tools are registered with the communicator using the `register_tool` method. The tool handler function:

1. Receives a payload dictionary containing the arguments
2. Processes the input data
3. Returns a result dictionary that will be sent back to the client

With MCP 1.7.1, it's important to handle different argument formats:
- Direct arguments like `payload["text"]`
- Content array format like `payload["content"][0]["text"]`

### Tool Calling

When calling a tool with MCP 1.7.1, it's best to provide arguments in multiple formats to ensure compatibility:

```python
payload = {
    "text": "Hello world",
    "content": [{"type": "text", "text": "Hello world"}]
}
```

### Error Handling

Proper error handling is crucial when working with network-based communication. Always use:

1. Timeouts to prevent hanging
2. Try/except blocks to catch and handle errors
3. Proper logging to aid in debugging

## Best Practices for MCP 1.7.1 SSE Communication

1. **Flexible Argument Handling**: Always check for arguments in multiple formats
2. **Robust Error Handling**: Handle all network and protocol errors gracefully
3. **Timeouts**: Use timeouts for all network operations to prevent hanging
4. **Graceful Shutdown**: Always stop the server properly to release resources
5. **Detailed Logging**: Log all operations to aid in debugging

## Troubleshooting

If you encounter issues:

1. **Connection Refused**: Make sure the server is running and the port is correct
2. **Tool Not Found**: Verify the tool name matches between provider and user
3. **Timeout Errors**: Increase the timeout value or check for network issues
4. **Serialization Errors**: Ensure all data sent and received is JSON-serializable
5. **Event Loop Errors**: These can occur during cleanup but are typically harmless

## Next Steps

- Try modifying the tool to perform different text processing operations
- Add more tools to the provider agent
- Implement a more complex application using multiple tools
- Explore the stdio transport for local communication in [MCP Stdio Tool Call Tutorial](mcp_stdio_tool_call_tutorial.md)

For more details on MCP integration in OpenMAS, see the [MCP Integration Guide](mcp_integration.md) and the [MCP Developer Guide](mcp_developer_guide.md).
