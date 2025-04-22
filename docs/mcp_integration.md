# MCP Integration in SimpleMAS

SimpleMAS provides seamless integration with the Model Context Protocol (MCP) through the specialized `McpAgent` class and decorators. This allows you to create MCP-compatible agents with minimal effort.

## Overview

MCP (Model Context Protocol) is a protocol for building model-backed applications. It's particularly useful for integrating LLMs like Claude into your applications. SimpleMAS provides a straightforward way to create MCP-compatible agents by:

1. Decorating methods with `@mcp_tool`, `@mcp_prompt`, or `@mcp_resource`
2. Creating a subclass of `McpAgent`
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

## Creating an MCP Server Agent

To create an agent that acts as an MCP server:

```python
from simple_mas.agent import McpAgent, mcp_tool
from simple_mas.communication.mcp import McpSseCommunicator

class MyServerAgent(McpAgent):
    def __init__(self, name):
        super().__init__(name=name)

        # Set up an MCP communicator in server mode
        self.set_communicator(McpSseCommunicator(
            agent_name=self.name,
            service_urls={},
            server_mode=True,  # This is critical for running as a server
            http_port=8000
        ))

    @mcp_tool(description="Add two numbers")
    async def add(self, a: int, b: int) -> dict:
        """Add two numbers and return the result."""
        result = a + b
        return {"sum": result}

    @mcp_prompt(description="Math problem solver prompt")
    async def math_problem_prompt(self, problem: str) -> str:
        return f"""
        Please solve the following math problem:

        {problem}

        Show your work and explain each step.
        """

    @mcp_resource(uri="/help", mime_type="text/html")
    async def help_resource(self) -> bytes:
        return b"""
        <html>
            <body>
                <h1>MCP Server Help</h1>
                <p>This server provides tools for mathematical operations.</p>
            </body>
        </html>
        """

# Create and start the agent
async def main():
    agent = MyServerAgent("math-server")
    await agent.start()

    # Keep the agent running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## How It Works

When you create a subclass of `McpAgent` and apply the MCP decorators to its methods:

1. The decorators store metadata on the methods
2. When the agent is initialized, it scans for decorated methods using `_discover_mcp_methods()`
3. When the agent is started with an MCP communicator in server mode, it registers the discovered methods with the MCP server during the `setup()` phase

The entire process is automatic - you just need to decorate your methods and make sure to use an MCP communicator in server mode.

## Best Practices

1. **Always provide descriptive docstrings** for your methods - they'll be used as descriptions if not explicitly provided
2. **Be specific with parameter types** - this helps with automatic Pydantic model generation
3. **Return structured data from tools** - preferably dictionaries that can be easily converted to JSON
4. **Keep prompt templates simple** and avoid complex logic in prompt methods
5. **Use resource URIs that follow RESTful conventions** - e.g., `/users/{id}` for resources that represent users

## Communicators

SimpleMAS offers two MCP communicators:

- `McpSseCommunicator`: Uses HTTP/SSE for communication (recommended for production)
- `McpStdioCommunicator`: Uses stdin/stdout for communication (useful for development)

Both can be used in server mode by setting `server_mode=True` when initializing them.

## Advanced Usage

For more advanced use cases, you can:

- Directly interact with the underlying FastMCP instance through `agent.communicator.mcp_server`
- Implement custom validation logic in your tool methods
- Create dynamic resources that generate content on-the-fly
- Use asynchronous processing for long-running operations

## Debugging

If you're having issues with your MCP agent:

1. Enable debug logging with `log_level="DEBUG"` when initializing your agent
2. Check if your decorators are being discovered with `self.logger.debug(f"Tools: {self._tools}")`
3. Ensure your communicator is set to server mode
4. Verify that your methods have the correct signatures and return types
