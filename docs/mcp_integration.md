# MCP Integration in SimpleMAS

SimpleMAS provides seamless integration with the Model Context Protocol (MCP) through the specialized `McpAgent` class and its subclasses, along with convenient decorators. This allows you to create MCP-compatible agents with minimal effort.

## Overview

MCP (Model Context Protocol) is a protocol for building model-backed applications. It's particularly useful for integrating LLMs like Claude into your applications. SimpleMAS provides a straightforward way to create MCP-compatible agents by:

1. Decorating methods with `@mcp_tool`, `@mcp_prompt`, or `@mcp_resource`
2. Creating a subclass of `McpAgent`, `McpClientAgent`, or `McpServerAgent`
3. Using an MCP-compatible communicator (such as `McpSseCommunicator` or `McpStdioCommunicator`)

## MCP Decorators

SimpleMAS provides three decorators for defining MCP functionality:

### Tool Decorator

The `@mcp_tool` decorator marks a method as an MCP tool, which can be called by clients:

```python
from simple_mas.agent import McpAgent, mcp_tool

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

SimpleMAS offers two approaches to create an MCP server:

### Using McpServerAgent (Recommended)

The simplest way to create an MCP server is to use the specialized `McpServerAgent` class:

```python
from simple_mas.agent import McpServerAgent, mcp_tool

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
from simple_mas.agent import McpAgent, mcp_tool
from simple_mas.communication.mcp import McpSseCommunicator

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

The `McpClientAgent` class provides convenient methods for working with MCP servers:

```python
from simple_mas.agent import McpClientAgent
from simple_mas.communication.mcp import McpSseCommunicator

async def main():
    # Create a client agent
    client = McpClientAgent(name="math-client")

    # Set a communicator
    client.set_communicator(McpSseCommunicator(
        agent_name=client.name,
        service_urls={}  # We'll add connections dynamically
    ))

    await client.communicator.start()

    # Connect to a server
    await client.connect_to_service("math-server", "localhost", 8000)

    # List available tools
    tools = await client.list_tools("math-server")
    print(f"Available tools: {tools}")

    # Call a tool
    result = await client.call_tool("math-server", "add", {"a": 5, "b": 3})
    print(f"5 + 3 = {result['sum']}")

    # Disconnect and stop
    await client.disconnect_from_service("math-server")
    await client.communicator.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## How It Works

The process of creating and running an MCP agent involves several components working together:

1. **Decorators**: `@mcp_tool`, `@mcp_prompt`, and `@mcp_resource` store metadata on the methods they decorate
2. **McpAgent**: Discovers decorated methods during initialization using `_discover_mcp_methods()`
3. **Communicators**: When in server mode, the communicator (either `McpSseCommunicator` or `McpStdioCommunicator`) registers the agent's tools, prompts, and resources with the underlying MCP server during its `start()` method

This design provides a clean separation of concerns:

- The agent is responsible for discovering and exposing functionality
- The communicator handles the actual server setup and communication
- The decorators provide a clear, declarative way to define MCP-compatible methods

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

## Communicators

SimpleMAS offers two MCP communicators:

- `McpSseCommunicator`: Uses HTTP/SSE for communication (recommended for production)
- `McpStdioCommunicator`: Uses stdin/stdout for communication (useful for development)

Both can be used in server mode by setting `server_mode=True` when initializing them.

## Advanced Usage

For more advanced use cases, you can:

- Directly interact with the underlying FastMCP instance through `agent.communicator.server`
- Implement custom validation logic in your tool methods
- Create dynamic resources that generate content on-the-fly
- Use asynchronous processing for long-running operations

## Debugging

If you're having issues with your MCP agent:

1. Enable debug logging with `log_level="DEBUG"` when initializing your agent
2. Check if your decorators are being discovered with `self.logger.debug(f"Tools: {self._tools}")`
3. Ensure your communicator is set to server mode
4. Verify that your methods have the correct signatures and return types
