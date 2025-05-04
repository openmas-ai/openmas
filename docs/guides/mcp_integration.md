# MCP Integration in OpenMAS

OpenMAS provides seamless integration with the Model Context Protocol (MCP) through the specialized `McpAgent` class and its subclasses, along with convenient decorators. This allows you to create MCP-compatible agents with minimal effort.

## Overview

MCP (Model Context Protocol) is a protocol for building model-backed applications developed by Anthropic. It's particularly useful for integrating large language models like Claude into your applications. OpenMAS provides a straightforward way to create MCP-compatible agents by:

1. Decorating methods with `@mcp_tool`, `@mcp_prompt`, or `@mcp_resource`
2. Creating a subclass of `McpAgent`, `McpClientAgent`, or `McpServerAgent`
3. Using an MCP-compatible communicator (such as `McpSseCommunicator` or `McpStdioCommunicator`)

## Installation

To use MCP functionality, install OpenMAS with the MCP extras:

```bash
pip install openmas[mcp]
```

Or with Poetry:

```bash
poetry add openmas[mcp]
```

This will install the MCP SDK (`mcp` package version 1.6.0) as a dependency.

## MCP Decorators

OpenMAS provides three decorators for defining MCP functionality:

### Tool Decorator

The `@mcp_tool` decorator marks a method as an MCP tool, which can be called by clients:

```python
from openmas.agent import McpAgent, mcp_tool

class MyMcpAgent(McpAgent):
    @mcp_tool(name="optional_custom_name", description="Tool description")
    async def my_tool(self, param1: str, param2: int = 0) -> dict:
        """Tool that does something useful.

        This docstring will be used as the description if not provided in the decorator.
        """
        # Implementation
        return {"result": f"Processed {param1} with {param2}"}
```

You can optionally specify Pydantic models for input validation and output transformation:

```python
from pydantic import BaseModel

class ToolInput(BaseModel):
    param1: str
    param2: int = 0

class ToolOutput(BaseModel):
    result: str

class MyMcpAgent(McpAgent):
    @mcp_tool(
        description="Tool description",
        input_model=ToolInput,
        output_model=ToolOutput
    )
    async def my_tool(self, param1: str, param2: int = 0) -> dict:
        # Implementation
        return {"result": f"Processed {param1} with {param2}"}
```

If input/output models are not specified, the decorator will automatically generate them from the method's type hints.

### Prompt Decorator

The `@mcp_prompt` decorator marks a method as an MCP prompt:

```python
class MyMcpAgent(McpAgent):
    @mcp_prompt(name="optional_custom_name", description="Prompt description")
    async def my_prompt(self, context: str, question: str) -> str:
        """Generate a prompt for the LLM.

        This docstring will be used as the prompt template if not provided.
        """
        return f"""
        Context: {context}

        Question: {question}

        Answer:
        """
```

You can also provide a specific template parameter:

```python
class MyMcpAgent(McpAgent):
    @mcp_prompt(
        template="""
        Context: {{context}}

        Question: {{question}}

        Answer:
        """
    )
    async def my_prompt(self, context: str, question: str) -> str:
        # Implementation
        return f"""
        Context: {context}

        Question: {question}

        Answer:
        """
```

### Resource Decorator

The `@mcp_resource` decorator marks a method as an MCP resource:

```python
class MyMcpAgent(McpAgent):
    @mcp_resource(
        uri="/path/to/resource",
        name="optional_custom_name",
        description="Resource description",
        mime_type="application/json"
    )
    async def my_resource(self) -> bytes:
        """Serve some resource data.

        This docstring will be used as the description if not provided.
        """
        return b'{"data": "some resource content"}'
```

## Creating an MCP Server

OpenMAS offers two approaches to create an MCP server:

### Using McpServerAgent (Recommended)

The simplest way to create an MCP server is to use the specialized `McpServerAgent` class:

```python
from openmas.agent import McpServerAgent, mcp_tool

class MyServerAgent(McpServerAgent):
    def __init__(self, name="my-server"):
        super().__init__(
            name=name,
            server_type="sse",  # Can be "sse" or "stdio"
            port=8000
        )

    @mcp_tool(description="Add two numbers")
    async def add(self, a: int, b: int) -> dict:
        """Add two numbers and return the result."""
        result = a + b
        return {"sum": result}

# Create and start the agent
async def main():
    agent = MyServerAgent()
    await agent.setup_communicator()  # Set up the communicator
    await agent.start_server()        # Start the server

    # Keep the agent running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop_server()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Using McpAgent with a Communicator

For more control, you can use the base `McpAgent` class and manually configure the communicator:

```python
from openmas.agent import McpAgent, mcp_tool
from openmas.communication.mcp import McpSseCommunicator

class MyServerAgent(McpAgent):
    def __init__(self, name="my-server"):
        super().__init__(name=name)

        # Set up an MCP communicator in server mode
        communicator = McpSseCommunicator(
            agent_name=self.name,
            service_urls={},
            server_mode=True,  # This is critical for running as a server
            http_port=8000
        )
        self.set_communicator(communicator)

    @mcp_tool(description="Add two numbers")
    async def add(self, a: int, b: int) -> dict:
        """Add two numbers and return the result."""
        result = a + b
        return {"sum": result}

# Create and start the agent
async def main():
    agent = MyServerAgent()
    await agent.communicator.start()  # Start the server

    # Keep the agent running
    try:
        await agent.run()  # This will keep running until interrupted
    except KeyboardInterrupt:
        await agent.communicator.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Creating an MCP Client

To interact with an MCP server (like the `CalculatorAgent` above), you create a standard OpenMAS agent (`BaseAgent`) and configure it to use an MCP communicator (`McpSseCommunicator` or `McpStdioCommunicator`) in **client mode** (which is the default). There isn't a specific `McpClientAgent` class; you leverage the standard `BaseAgent`.

```python
import asyncio
from openmas.agent import BaseAgent  # Use BaseAgent for clients
from openmas.communication.mcp import McpSseCommunicator
from openmas.logging import configure_logging, get_logger
from openmas.exceptions import CommunicationError # Import relevant exceptions

configure_logging(log_level="INFO")
logger = get_logger(__name__)

class CalculatorClientAgent(BaseAgent): # Inherit from BaseAgent
    def __init__(self, name="calculator-client", server_url="http://localhost:8001"):
        super().__init__(name=name)
        logger.info(f"Initializing CalculatorClientAgent to connect to {server_url}")

        # Configure communicator for client mode
        communicator = McpSseCommunicator(
            agent_name=self.name,
            # Define the target service URL. The key ('calculator' here) is how
            # you refer to this service in send_request calls.
            service_urls={"calculator": server_url},
            server_mode=False # Explicitly client mode (default)
        )
        self.set_communicator(communicator)

    async def run(self) -> None:
        logger.info(f"Agent '{self.name}' running. Will call calculator server.")
        try:
            # In client mode, communicator.start() (called by agent.start())
            # mostly sets up internal state. Connections are typically made lazily
            # when send_request is first called for a service.

            # Call the 'add' tool on the 'calculator' service
            logger.info("Calling 'add' tool...")
            add_result = await self.communicator.send_request(
                target_service="calculator", # Use the key defined in service_urls
                method="add", # Corresponds to the @mcp_tool method name on the server
                params={"a": 10, "b": 5}
            )
            logger.info(f"Add Result: {add_result}") # Expected: {'result': 15}

            # Call the 'subtract' tool
            logger.info("Calling 'subtract' tool...")
            sub_result = await self.communicator.send_request(
                target_service="calculator",
                method="subtract",
                params={"a": 100, "b": 33}
            )
            logger.info(f"Subtract Result: {sub_result}") # Expected: {'result': 67}

        except CommunicationError as e: # Catch more specific errors if possible
            logger.error(f"Error during MCP request: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred in run: {e}", exc_info=True)
        finally:
            logger.info("Client run finished.")
            # In a real agent, this loop might wait for external triggers,
            # process incoming messages, or run periodically.
            # For this example, we exit after making the calls.
            # To keep it running indefinitely:
            # while True: await asyncio.sleep(3600)

async def main():
    # Ensure the CalculatorAgent server is running on localhost:8001 first!
    client_agent = CalculatorClientAgent(server_url="http://localhost:8001")

    try:
        # Start the agent. This calls agent.setup() and then agent.run()
        # The communicator's client-side setup happens within agent.start()
        await client_agent.start()
        # In this example, run() completes after making requests, so start() will return.

    except KeyboardInterrupt:
        logger.info("Client interrupted by user.")
    except Exception as e:
         logger.error(f"Client agent failed: {e}", exc_info=True)
    finally:
        # Stop the agent (calls agent.shutdown() which cleans up communicator)
        await client_agent.stop()
        logger.info("Client agent stopped.")

if __name__ == "__main__":
    # Optional: Add a small delay if running server & client almost simultaneously
    # import time
    # time.sleep(2) # Allow server time to bind port
    asyncio.run(main())
```

**To Run:**

1.  Make sure the `CalculatorAgent` server (from the previous section) is running.
2.  Save the client code above (e.g., `calculator_client.py`).
3.  Ensure `openmas[mcp]` is installed.
4.  Run `python calculator_client.py`.

You will see the client log messages as it calls the `add` and `subtract` tools on the server and prints the results.

## How It Works

The process of creating and running an MCP agent involves several components working together:

1. **Decorators**: `@mcp_tool`, `@mcp_prompt`, and `@mcp_resource` store metadata on the methods they decorate
2. **McpAgent**: Discovers decorated methods during initialization using `_discover_mcp_methods()`
3. **Communicators**: When in server mode, the communicator (either `McpSseCommunicator` or `McpStdioCommunicator`) registers the agent's tools, prompts, and resources with the underlying MCP server during its `start()` method

This design provides a clean separation of concerns:

- The agent is responsible for discovering and exposing functionality
- The communicator handles the actual server setup and communication
- The decorators provide a clear, declarative way to define MCP-compatible methods

## Available Communicators

OpenMAS offers two MCP communicators:

- `McpSseCommunicator`: Uses HTTP/SSE for communication over a network (recommended for production)
- `McpStdioCommunicator`: Uses stdin/stdout for communication (useful for local development or embedding)

Both can be used in server mode by setting `server_mode=True` when initializing them.

### McpSseCommunicator

This communicator uses HTTP/SSE (Server-Sent Events) for communication. It's suitable for networked applications where the MCP server and clients communicate over HTTP:

```python
from openmas.communication.mcp import McpSseCommunicator

# Server mode
server_communicator = McpSseCommunicator(
    agent_name="mcp-server",
    server_mode=True,
    http_port=8000,
    service_urls={}
)

# Client mode
client_communicator = McpSseCommunicator(
    agent_name="mcp-client",
    server_mode=False,
    service_urls={
        "mcp-server": "http://localhost:8000"
    }
)
```

### McpStdioCommunicator

This communicator uses stdin/stdout for communication, making it ideal for embedding within another application or for local development:

```python
from openmas.communication.mcp import McpStdioCommunicator

# Server mode (for receiving commands via stdin)
stdio_server = McpStdioCommunicator(
    agent_name="stdio-server",
    server_mode=True,
    service_urls={}
)

# Client mode (for calling tools on other MCP servers)
stdio_client = McpStdioCommunicator(
    agent_name="stdio-client",
    server_mode=False,
    service_urls={
        "tool_provider": "stdio:openmas run tool_provider"
    }
)
```

#### Working with McpStdioCommunicator

The stdio transport is particularly useful for:

1. **Tool providers as child processes**: A parent process can spawn a child process and communicate with it via stdio
2. **Command-line tools**: Making existing CLI tools accessible via MCP
3. **Local development**: Simple setup without network configuration
4. **Process isolation**: Running tool providers in separate processes for stability

#### Service URL Formats for stdio

When using `McpStdioCommunicator` in client mode, you need to specify service URLs that tell the communicator how to spawn the server process. The general format is:

```
stdio:<command>
```

Where `<command>` is the command to execute to start the server process. Several formats are supported:

| Format | Example | Description |
|--------|---------|-------------|
| `stdio:openmas` | `"stdio:openmas"` | Uses the OpenMAS CLI to launch the provider with default settings |
| `stdio:openmas run <agent>` | `"stdio:openmas run tool_provider"` | Explicit run command with agent name |
| `stdio:openmas run --project <path> <agent>` | `"stdio:openmas run --project /path/to/project tool_provider"` | With project path |
| `stdio:<executable>` | `"stdio:/path/to/executable"` | Direct path to an executable |
| `stdio:<interpreter> -m <module>` | `"stdio:python -m my_module"` | Custom interpreter and module command |

In production environments, you might want to use more specific paths:
```python
service_urls = {
    "tool_provider": "stdio:/usr/local/bin/openmas run tool_provider",
    "python_tool": "stdio:/path/to/venv/bin/python -m my_tool_provider"
}
```

#### Complete stdio Tool Call Example

Here's a complete example of a tool provider and user using the stdio transport:

**Tool Provider Agent:**

```python
from openmas.agent import McpServerAgent, mcp_tool

class ToolProviderAgent(McpServerAgent):
    def __init__(self, name="tool-provider"):
        super().__init__(
            name=name,
            server_type="stdio",  # Use stdio transport
        )

    @mcp_tool(description="Process incoming data and return a result")
    async def process_data(self, text: str = "") -> dict:
        """Process incoming data and return a result.

        Args:
            text: The text to process

        Returns:
            Dictionary with processed results
        """
        if text:
            processed_text = text.upper()
            word_count = len(text.split())

            return {
                "processed_text": processed_text,
                "word_count": word_count,
                "status": "success"
            }
        else:
            return {
                "error": "No text provided",
                "status": "error"
            }

# Run the server
if __name__ == "__main__":
    import asyncio

    async def main():
        agent = ToolProviderAgent()
        await agent.setup()
        await agent.start_server()

        try:
            # Keep the server running until interrupted
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await agent.shutdown()

    asyncio.run(main())
```

**Tool User Agent:**

```python
from openmas.agent import BaseAgent
import asyncio

class ToolUserAgent(BaseAgent):
    def __init__(self, name="tool-user", provider_command="openmas run tool_provider"):
        super().__init__(name=name)

        # Configure the communicator
        from openmas.communication.mcp import McpStdioCommunicator
        communicator = McpStdioCommunicator(
            agent_name=self.name,
            server_mode=False,  # Client mode
            service_urls={
                "tool_provider": f"stdio:{provider_command}"
            }
        )
        self.set_communicator(communicator)

    async def run(self):
        try:
            # Call the process_data tool
            result = await self.communicator.call_tool(
                target_service="tool_provider",
                tool_name="process_data",
                arguments={"text": "Hello, this is a test message."}
            )

            print(f"Tool call result: {result}")

            # Check for success
            if result.get("status") == "success":
                print(f"Processed text: {result.get('processed_text')}")
                print(f"Word count: {result.get('word_count')}")
            else:
                print(f"Error: {result.get('error')}")

        except Exception as e:
            print(f"Error calling tool: {e}")

# Run the client
if __name__ == "__main__":
    import asyncio

    async def main():
        agent = ToolUserAgent()
        await agent.setup()
        await agent.run()
        await agent.shutdown()

    asyncio.run(main())
```

#### Timeout Handling with McpStdioCommunicator

When working with stdio transport, proper timeout handling is essential to avoid hanging or deadlocked processes. There are two main approaches:

1. **Using asyncio.wait_for():**

```python
import asyncio

try:
    # Set a timeout for the tool call
    timeout_seconds = 5.0
    result = await asyncio.wait_for(
        self.communicator.call_tool(
            target_service="tool_provider",
            tool_name="process_data",
            arguments={"text": "test message"}
        ),
        timeout=timeout_seconds
    )
except asyncio.TimeoutError:
    print(f"Tool call timed out after {timeout_seconds} seconds")
    # Implement recovery logic here
```

2. **Implementing a timeout wrapper method:**

```python
async def call_tool_with_timeout(
    self, target_service: str, tool_name: str, arguments: dict, timeout: float
) -> dict:
    """Call a tool with a timeout to prevent hanging.

    Args:
        target_service: Service providing the tool
        tool_name: Name of the tool to call
        arguments: Tool arguments
        timeout: Timeout in seconds

    Returns:
        Tool result

    Raises:
        asyncio.TimeoutError: If the call times out
    """
    return await asyncio.wait_for(
        self.communicator.call_tool(
            target_service=target_service,
            tool_name=tool_name,
            arguments=arguments
        ),
        timeout=timeout
    )
```

#### Troubleshooting MCP stdio Communication

When working with stdio transport, you might encounter these common issues:

1. **Process Execution Issues:**
   - **Symptom:** `FileNotFoundError` or `PermissionError`
   - **Cause:** Invalid executable path or permissions
   - **Solution:** Verify the executable path is correct and has execution permissions

2. **Initialization Timeout:**
   - **Symptom:** Tool calls hang or time out during initialization
   - **Cause:** The provider process might be starting slowly or not registering tools properly
   - **Solution:**
     - Add logging to verify tool registration
     - Increase initialization timeout
     - Check for errors in the provider process

3. **Process Termination:**
   - **Symptom:** `BrokenPipeError` or `ConnectionResetError`
   - **Cause:** The provider process exited unexpectedly
   - **Solution:**
     - Add error handling to restart the process if needed
     - Verify the provider process stays alive while waiting for tool calls

4. **Tool Name Mismatches:**
   - **Symptom:** "Tool not found" errors
   - **Cause:** The name used when calling a tool doesn't match the registered name
   - **Solution:** Ensure consistent tool naming between registration and calls

#### Debugging Tips for stdio Transport

1. **Enable Debug Logging:**
   ```python
   # For OpenMAS communicator
   communicator = McpStdioCommunicator(
       agent_name="agent",
       log_level="DEBUG",
       # other options...
   )

   # For underlying MCP
   import logging
   logging.basicConfig(
       level=logging.DEBUG,
       format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
   )
   ```

2. **Capture Process Output:**
   ```python
   # When starting a process manually
   process = await asyncio.create_subprocess_exec(
       *cmd,
       stdout=asyncio.subprocess.PIPE,
       stderr=asyncio.subprocess.PIPE,
   )

   # Read process output for debugging
   stderr_data = await process.stderr.read(1024)
   print(f"Process error output: {stderr_data.decode()}")
   ```

3. **Test with MCP Inspector:**
   The MCP package includes an inspector tool for debugging:
   ```bash
   # Install MCP with CLI tools
   pip install "mcp[cli]"

   # Run the inspector on your server
   mcp dev --stdio-command "openmas run tool_provider"
   ```

4. **Verify Process Management:**
   ```python
   # Check if the provider process is still running
   if provider_process and provider_process.returncode is not None:
       logger.error(f"Provider process exited with code {provider_process.returncode}")
       # Implement restart logic if needed
   ```

## Best Practices

1. **Choose the right agent class for your needs**:
   - Use `McpServerAgent` for servers
   - Use `McpClientAgent` for clients
   - Use `McpAgent` directly for hybrid cases or when you need maximum flexibility

2. **Always provide descriptive docstrings** for your methods - they'll be used as descriptions if not explicitly provided
3. **Be specific with parameter types** - this helps with automatic Pydantic model generation
4. **Return structured data from tools** - preferably dictionaries that can be easily converted to JSON
5. **Keep prompt templates simple** and avoid complex logic in prompt methods
6. **Use resource URIs that follow RESTful conventions** - e.g., `/users/{id}` for resources that represent users

## Debugging

If you're having issues with your MCP agent:

1. Enable debug logging with `log_level="DEBUG"` when initializing your agent
2. Check if your decorators are being discovered with `self.logger.debug(f"Tools: {self._tools}")`
3. Ensure your communicator is set to server mode
4. Verify that your methods have the correct signatures and return types

## Testing MCP Agents

OpenMAS provides testing utilities specifically for MCP agents:

```python
import pytest
from openmas.testing import AgentTestHarness
from openmas.agent import McpServerAgent

class TestMcpAgent(McpServerAgent):
    # Your test agent implementation
    pass

@pytest.fixture
async def mcp_agent_harness():
    # Create the test harness
    harness = AgentTestHarness(TestMcpAgent)
    yield harness

@pytest.mark.asyncio
async def test_mcp_tool_calls(mcp_agent_harness):
    # Create and start the agent
    agent = await mcp_agent_harness.create_agent()

    async with mcp_agent_harness.running_agent(agent):
        # Test MCP tool calls
        pass
```

For more information on testing, see the [Testing Utilities Guide](testing-utilities.md) documentation.
