# MCP stdio Tool Call Tutorial

This tutorial walks you through creating a simple OpenMAS project that demonstrates MCP tool calls over standard input/output (stdio). You'll build a tool provider agent that exposes a text processing tool, and a tool user agent that calls this tool.

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
```

**agents/tool_user/__init__.py**:
```python
"""Tool user agent package."""
```

## Step 1: Implement the Tool Provider Agent

Create the tool provider agent that registers and exposes an MCP tool:

**agents/tool_provider/agent.py**:
```python
"""Tool provider agent that registers and exposes an MCP tool via stdio."""

import asyncio
from typing import Any, Dict

from openmas.agent import BaseAgent
from openmas.logging import get_logger

logger = get_logger(__name__)


class ToolProviderAgent(BaseAgent):
    """Agent that provides an MCP tool over stdio.

    This agent registers a tool called "process_data" that handles
    incoming data and returns a processed result.
    """

    async def setup(self) -> None:
        """Set up the agent by registering the MCP tool."""
        logger.info("Setting up ToolProviderAgent")

        # Register the process_data tool with the MCP communicator
        await self.communicator.register_tool(
            name="process_data",
            description="Process incoming data and return a result",
            function=self.process_data_handler,
        )
        logger.info("Registered MCP tool: process_data")
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

        The tool provider agent doesn't need to actively do anything in its run method.
        It primarily waits for incoming tool calls and responds to them.
        """
        logger.info("ToolProviderAgent running, waiting for tool calls")

        # Keep the agent alive while waiting for tool calls
        while True:
            await asyncio.sleep(1)

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

logger = get_logger(__name__)


class ToolUserAgent(BaseAgent):
    """Agent that uses an MCP tool over stdio.

    This agent calls the "process_data" tool provided by the ToolProviderAgent,
    sends some text data, and processes the result.
    """

    async def setup(self) -> None:
        """Set up the agent."""
        logger.info("Setting up ToolUserAgent")
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[Dict[str, str]] = None
        logger.info("ToolUserAgent setup complete")

    async def run(self) -> None:
        """Run the agent by calling the process_data tool."""
        logger.info("ToolUserAgent running, calling process_data tool")

        # Prepare the data to send to the tool
        tool_payload = {"text": "Hello, this is a sample text that needs processing."}
        tool_name = "process_data"

        try:
            # Set a timeout for the tool call to prevent hanging
            timeout_seconds = 10.0

            logger.info(f"Calling tool '{tool_name}' with payload: {tool_payload}")

            # Call the process_data tool using MCP call_tool with timeout
            result = await self._call_tool_with_timeout(
                target_service="tool_provider",
                tool_name=tool_name,
                arguments=tool_payload,
                timeout=timeout_seconds
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
        """
        return await asyncio.wait_for(
            self.communicator.call_tool(target_service=target_service, tool_name=tool_name, arguments=arguments),
            timeout=timeout,
        )

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
description: "Example demonstrating MCP tool calls over standard input/output (stdio)"

# Define the available agents
agents:
  tool_provider: "agents/tool_provider"
  tool_user: "agents/tool_user"

# Default configuration for all agents
default_config:
  log_level: INFO

# Default communicator settings
communicator_defaults:
  type: mcp-stdio
  options:
    server_mode: false

# Agent-specific configurations
agent_configs:
  # Tool provider config - run in server mode to expose tools
  tool_provider:
    communicator_options:
      server_mode: true
      server_instructions: "A service that processes text using an MCP tool"

  # Tool user config - client mode with service URLs to find the tool provider
  tool_user:
    service_urls:
      # Service URL for the tool provider
      # This tells the tool user how to spawn the provider process
      tool_provider: "stdio:openmas run tool_provider"
```

## Step 4: Create a README

Document your project with a README file:

**README.md**:
```markdown
# MCP Tool Call over stdio Example

This example demonstrates how to use MCP (Model Context Protocol) tool calls over standard input/output (stdio) in OpenMAS. It showcases how one agent can define an MCP tool and another agent can call that tool, with the communication happening over stdio streams.

## Running the Example

To run this example, you'll need to have OpenMAS installed with the MCP extras:

```bash
pip install "openmas[mcp]"
```

Then, you can run the example using the OpenMAS CLI:

```bash
openmas run
```

This will start both agents and you'll see the logs showing the tool registration, call, and response.
```

## Step 5: Run the Example

Now you can run the example using the OpenMAS CLI:

```bash
openmas run
```

You should see output similar to this:

```
INFO - Setting up ToolProviderAgent
INFO - Registered MCP tool: process_data
INFO - ToolProviderAgent setup complete
INFO - ToolProviderAgent running, waiting for tool calls
INFO - Setting up ToolUserAgent
INFO - ToolUserAgent setup complete
INFO - ToolUserAgent running, calling process_data tool
INFO - Calling tool 'process_data' with payload: {'text': 'Hello, this is a sample text that needs processing.'}
INFO - Tool handler received data: {'text': 'Hello, this is a sample text that needs processing.'}
INFO - Tool handler returning result: {'processed_text': 'HELLO, THIS IS A SAMPLE TEXT THAT NEEDS PROCESSING.', 'word_count': 9, 'status': 'success'}
INFO - Received tool result: {'processed_text': 'HELLO, THIS IS A SAMPLE TEXT THAT NEEDS PROCESSING.', 'word_count': 9, 'status': 'success'}
INFO - Successfully processed text. Word count: 9
INFO - Processed text: HELLO, THIS IS A SAMPLE TEXT THAT NEEDS PROCESSING.
INFO - ToolUserAgent completed its run method
```

## Step 6: Experimenting with the Example

### Modifying the Tool Logic

You can modify the `process_data_handler` method in the `ToolProviderAgent` to add more functionality. For example, you could add:

- Text summarization
- Sentiment analysis
- Translation
- Entity extraction

Simply update the handler to process the text differently:

```python
async def process_data_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle incoming tool calls by processing the provided data."""
    logger.info(f"Tool handler received data: {payload}")

    if "text" in payload:
        text = payload["text"]

        # Multiple processing options
        processed_text = text.upper()
        word_count = len(text.split())
        character_count = len(text)
        reversed_text = text[::-1]

        result = {
            "processed_text": processed_text,
            "word_count": word_count,
            "character_count": character_count,
            "reversed_text": reversed_text,
            "status": "success"
        }
    else:
        result = {"error": "No text field in payload", "status": "error"}

    logger.info(f"Tool handler returning result: {result}")
    return result
```

### Adding Timeout Handling

You can experiment with timeout handling by modifying the `process_data_handler` to simulate a slow operation:

```python
async def process_data_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle incoming tool calls by processing the provided data."""
    logger.info(f"Tool handler received data: {payload}")

    # Simulate a slow operation
    await asyncio.sleep(5.0)  # Sleep for 5 seconds

    if "text" in payload:
        processed_text = payload["text"].upper()
        word_count = len(payload["text"].split())

        result = {"processed_text": processed_text, "word_count": word_count, "status": "success"}
    else:
        result = {"error": "No text field in payload", "status": "error"}

    logger.info(f"Tool handler returning result: {result}")
    return result
```

Then adjust the timeout in the `ToolUserAgent` to see how it handles timeouts:

```python
# Change to a shorter timeout to trigger a timeout error
timeout_seconds = 2.0  # 2-second timeout (shorter than the 5-second sleep)
```

## Conclusion

You've successfully created an OpenMAS project that demonstrates MCP tool calls over stdio. This pattern can be extended to implement more complex tool providers and users, enabling efficient communication between agents using the Model Context Protocol.

Some ways to extend this example:

1. Add more tools to the provider agent
2. Implement multiple tool providers
3. Create a chain of tool calls where one agent calls another
4. Integrate with external systems using tools
5. Add authentication or validation to the tool calls

For more information on MCP integration in OpenMAS, see the [MCP Integration Guide](mcp_integration.md).
