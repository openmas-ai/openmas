# MCP STDIO Tool Call Tutorial

This tutorial walks you through creating a simple OpenMAS project that demonstrates MCP tool calls over standard input/output (STDIO). You'll build a tool provider agent that exposes a text processing tool, and a tool user agent that calls this tool.

## Prerequisites

- Python 3.10 or higher
- Poetry (recommended) or pip
- OpenMAS with MCP extras installed

If you haven't installed OpenMAS with MCP extras yet:

```bash
# With poetry
poetry add "openmas[mcp]"

# With pip
pip install "openmas[mcp]"
```

Ensure you have MCP 1.7.1 or later:

```bash
# With poetry
poetry add "mcp>=1.7.1"

# With pip
pip install "mcp>=1.7.1"
```

## Project Setup

1. Create a new project directory:

```bash
mkdir mcp_stdio_example
cd mcp_stdio_example
```

2. Create the project structure:

```bash
mkdir -p agents/tool_provider agents/tool_user config
touch openmas_project.yml
touch agents/tool_provider/__init__.py
touch agents/tool_provider/agent.py
touch agents/tool_user/__init__.py
touch agents/tool_user/agent.py
touch README.md
```

3. Initialize the `__init__.py` files:

**agents/tool_provider/__init__.py**:
```python
"""Tool provider agent package."""

from .agent import ToolProviderAgent
```

**agents/tool_user/__init__.py**:
```python
"""Tool user agent package."""

from .agent import ToolUserAgent
```

## Step 1: Implement the Tool Provider Agent

Create the tool provider agent that registers and exposes an MCP tool:

**agents/tool_provider/agent.py**:
```python
"""Tool provider agent that registers and exposes an MCP tool via stdio."""

import asyncio
from typing import Any, Dict, List

from openmas.agent import BaseAgent
from openmas.logging import get_logger

# Import MCP types if available, otherwise use Any
try:
    from mcp.types import TextContent
    HAS_MCP_TYPES = True
except ImportError:
    HAS_MCP_TYPES = False
    TextContent = Any  # type: ignore

logger = get_logger(__name__)


class ToolProviderAgent(BaseAgent):
    """Agent that provides an MCP tool over stdio.

    This agent registers a tool called "process_text" that handles
    incoming text and returns a processed result.
    """

    async def setup(self) -> None:
        """Set up the agent by registering the MCP tool."""
        logger.info("Setting up ToolProviderAgent")

        # Register the process_text tool with the MCP communicator
        await self.communicator.register_tool(
            name="process_text",
            description="Process incoming text and return a result",
            function=self.process_text_handler,
        )
        logger.info("Registered MCP tool: process_text")
        logger.info("ToolProviderAgent setup complete")

    async def process_text_handler(self, payload: Dict[str, Any]) -> List[Any]:
        """Handle incoming tool calls by processing the provided text.

        Args:
            payload: Dictionary containing the text to process

        Returns:
            List of TextContent objects containing the processed result
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
            error_msg = "No text field found in payload"
            logger.error(f"{error_msg}: {payload}")

            # Return error message as TextContent for MCP 1.7.1
            if HAS_MCP_TYPES:
                import json
                return [TextContent(type="text", text=json.dumps({"error": error_msg, "status": "error"}))]
            else:
                # Fallback for when TextContent is not available (testing)
                return [{"type": "text", "text": f'{{"error": "{error_msg}", "status": "error"}}'}]

        # Simple processing - convert to uppercase and count words
        processed_text = text.upper()
        word_count = len(text.split())

        # Format the result according to MCP 1.7.1 requirements
        import json
        result_json = json.dumps({
            "processed_text": processed_text,
            "word_count": word_count,
            "status": "success"
        })

        logger.info(f"Tool handler returning result: {result_json}")

        # Return the result as TextContent for MCP 1.7.1
        if HAS_MCP_TYPES:
            return [TextContent(type="text", text=result_json)]
        else:
            # Fallback for when TextContent is not available (testing)
            return [{"type": "text", "text": result_json}]

    async def run(self) -> None:
        """Run the agent.

        The tool provider agent doesn't need to actively do anything in its run method.
        It primarily waits for incoming tool calls and responds to them.
        """
        logger.info("ToolProviderAgent running, waiting for tool calls")

        # Keep the agent alive while waiting for tool calls
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Tool provider run loop cancelled")
            raise

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info("ToolProviderAgent shutting down")
```

## Step 2: Implement the Tool User Agent

Create the tool user agent that calls the tool exposed by the provider:

**agents/tool_user/agent.py**:
```python
"""Tool user agent that calls an MCP tool via stdio."""

import asyncio
from typing import Any, Dict, Optional

from openmas.agent import BaseAgent
from openmas.logging import get_logger
from openmas.exceptions import CommunicationError

logger = get_logger(__name__)


class ToolUserAgent(BaseAgent):
    """Agent that uses an MCP tool over stdio.

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

## Step 3: Configure the Project

Create the OpenMAS project configuration:

**openmas_project.yml**:
```yaml
name: mcp_stdio_tool_call_example
version: 0.1.0
description: "Example demonstrating MCP tool calls over standard input/output (stdio) using MCP 1.7.1"

# Define the available agents
agents:
  tool_provider: "agents/tool_provider"
  tool_user: "agents/tool_user"

# Default configuration for all agents
default_config:
  log_level: INFO

# Default communicator settings
communicator_defaults:
  type: mock
  options: {}

# Agent-specific configurations
agent_configs:
  # Tool provider config
  tool_provider:
    communicator_type: mcp-stdio
    communicator_options:
      server_mode: true

  # Tool user config
  tool_user:
    communicator_type: mcp-stdio
    communicator_options:
      server_mode: false
    service_urls:
      # The command to start the tool provider (uses openmas run)
      tool_provider: "poetry run openmas run tool_provider --project ."
```

## Step 4: Create a Test Script

Create a test script to verify that the example works:

**test_example.py**:
```python
"""Test script for the MCP STDIO tool call example."""

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
    logger.info("Starting MCP STDIO tool call test")

    # Create the agent factory
    factory = AgentFactory()

    # Create the agents
    tool_user = await factory.create_agent("tool_user")

    try:
        # Start the user agent - it will start the provider
        # as a subprocess using the command in service_urls
        await tool_user.start()
        logger.info("Tool user agent started")

        # Wait for the user to complete its task
        await asyncio.sleep(5.0)

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

### Method 1: Run Each Agent Separately

1. First, start the tool provider:

```bash
poetry run openmas run tool_provider
```

2. Then, in a separate terminal, start the tool user:

```bash
poetry run openmas run tool_user
```

### Method 2: Use the Test Script

```bash
python test_example.py
```

## Key Concepts

### MCP STDIO Communicator

The `McpStdioCommunicator` handles communication over standard input/output pipes:

1. In server mode, it listens for incoming messages on stdin
2. In client mode, it starts the server as a subprocess and connects via pipes
3. All MCP protocol messages are exchanged via these pipes

### MCP 1.7.1 Tool Response Format

With MCP 1.7.1, tools must return a list of `TextContent` objects:

```python
from mcp.types import TextContent
import json

# Convert a dictionary to a valid MCP 1.7.1 response
result_dict = {"processed_text": "HELLO", "word_count": 1, "status": "success"}
json_str = json.dumps(result_dict)
response = [TextContent(type="text", text=json_str)]
```

### Tool Input Format

For maximum compatibility, provide arguments in multiple formats:

```python
payload = {
    "text": "Hello world",
    "content": [{"type": "text", "text": "Hello world"}]
}
```

## Best Practices for MCP 1.7.1 STDIO Communication

1. **Handle Different Argument Formats**: Check for arguments in both direct and content array formats
2. **Proper Return Format**: Return a list of TextContent objects
3. **Structured Responses**: Use JSON for structured data exchange
4. **Error Handling**: Catch and handle errors gracefully
5. **Timeouts**: Use timeouts to prevent hanging when calling tools

## Troubleshooting

1. **Process Startup Errors**: If the provider process fails to start, check:
   - Correct command in service_urls
   - Permission issues
   - Path issues

2. **Communication Errors**: If tool calls fail:
   - Check that tools are registered with the correct names
   - Verify that arguments are formatted correctly
   - Look for serialization errors in complex data

3. **Timeout Issues**: If calls timeout:
   - Increase the timeout value
   - Check for performance issues in tool implementation
   - Ensure the provider is not deadlocked

## Comparison of STDIO vs SSE

| Feature | STDIO | SSE |
|---------|-------|-----|
| Communication | Process-based (pipes) | Network-based (HTTP) |
| Multiple Clients | One client per provider | Multiple clients per server |
| Deployment | Must run on same machine | Can run on different machines |
| Setup | Simpler (process pipes) | More complex (HTTP server) |
| Resilience | Process must restart on failure | Can reconnect on failure |
| Use Case | Local tool execution | Distributed systems |

## Next Steps

- Add more tools to the provider
- Process more complex data types
- Implement error handling for edge cases
- Try the SSE transport for networked communication in [MCP SSE Tool Call Tutorial](mcp_sse_tool_call_tutorial.md)

For more details on MCP integration in OpenMAS, see the [MCP Integration Guide](mcp_integration.md) and the [MCP Developer Guide](mcp_developer_guide.md).
