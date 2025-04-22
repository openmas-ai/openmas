# MCP Agent Integration

SimpleMAS provides seamless integration with the Model Context Protocol (MCP) through the specialized `McpAgent` class and decorators. This allows you to create MCP-compatible agents with minimal effort.

## MCP Decorators

SimpleMAS provides three decorators for defining MCP functionality:

- `@mcp_tool`: Mark a method as an MCP tool, which can be called by clients.
- `@mcp_prompt`: Mark a method as an MCP prompt, which can be used for LLM prompting.
- `@mcp_resource`: Mark a method as an MCP resource, which serves static or dynamic content.

### Tool Decorator

The `@mcp_tool` decorator marks a method as an MCP tool:

```python
@mcp_tool(name="optional_custom_name", description="Tool description")
async def my_tool(self, param1: str, param2: int = 0) -> dict:
    # Implementation
    return {"result": "value"}
```

You can optionally specify Pydantic models for input validation and output transformation:

```python
@mcp_tool(
    description="Tool description",
    input_model=MyInputModel,
    output_model=MyOutputModel
)
async def my_tool(self, param1: str, param2: int = 0) -> dict:
    # Implementation
    return {"result": "value"}
```

If input/output models are not specified, the decorator will try to generate them from the method's type hints.

### Prompt Decorator

The `@mcp_prompt` decorator marks a method as an MCP prompt:

```python
@mcp_prompt(name="optional_custom_name", description="Prompt description")
async def my_prompt(self, param1: str, param2: int = 0) -> str:
    # Implementation
    return "Generated text"
```

### Resource Decorator

The `@mcp_resource` decorator marks a method as an MCP resource:

```python
@mcp_resource(
    uri="/path/to/resource",
    name="optional_custom_name",
    description="Resource description",
    mime_type="application/json"
)
async def my_resource(self) -> bytes:
    # Implementation
    return b"Resource content"
```

## McpAgent Class

The `McpAgent` class extends `BaseAgent` with MCP-specific functionality, automatically discovering decorated methods and registering them with an MCP server when using an MCP communicator in server mode.

### Key Features

- Automatic discovery and registration of MCP-decorated methods
- Integration with MCP server functionality
- Type validation through Pydantic models
- Support for both SSE and STDIO communication

## Example Usage

Here's an example of a simple MCP agent:

```python
from simple_mas.agent import McpAgent, mcp_tool, mcp_prompt, mcp_resource
from typing import List

class WeatherAgent(McpAgent):
    @mcp_tool(description="Get weather forecast for a location")
    async def get_weather(self, location: str, days: int = 1) -> dict:
        # Implementation...
        return {"location": location, "forecast": [...]}

    @mcp_prompt(description="Generate a travel itinerary")
    async def generate_itinerary(self, destination: str, days: int, interests: List[str]) -> str:
        # Implementation...
        return "Sample itinerary..."

    @mcp_resource(uri="/logo", description="Agent logo", mime_type="image/png")
    async def get_logo(self) -> bytes:
        # Implementation...
        return b"Sample image data"
```

## Starting an MCP Server

To run your agent as an MCP server:

```python
import asyncio
from simple_mas.communication.mcp import McpSseCommunicator

async def main():
    # Create an MCP SSE communicator in server mode
    communicator = McpSseCommunicator(
        agent_name="weather_agent",
        service_urls={},
        server_mode=True,
        http_port=8000
    )

    # Create and start the agent
    agent = WeatherAgent("weather_agent")
    agent.set_communicator(communicator)
    await agent.start()

    # Keep the server running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Type Hinting and Pydantic Models

You can use type hints and Pydantic models for automatic validation:

```python
from pydantic import BaseModel

class WeatherRequest(BaseModel):
    location: str
    days: int = 1

class WeatherResponse(BaseModel):
    location: str
    forecast: List[dict]

@mcp_tool(
    description="Get weather forecast",
    input_model=WeatherRequest,
    output_model=WeatherResponse
)
async def get_weather(self, location: str, days: int = 1) -> dict:
    # Implementation...
```

Alternatively, the decorators will automatically use type hints to create validation models when possible.

## Integration with Existing Agents

If you already have an agent that extends `BaseAgent`, you can switch to `McpAgent` to gain MCP capabilities:

```python
# Before:
class MyAgent(BaseAgent):
    # implementation

# After:
class MyAgent(McpAgent):
    # same implementation, plus MCP decorators
```

## Using Different MCP Communicators

SimpleMAS supports two types of MCP communicators:

### SSE Communicator

```python
from simple_mas.communication.mcp import McpSseCommunicator

communicator = McpSseCommunicator(
    agent_name="my_agent",
    service_urls={},
    server_mode=True,
    http_port=8000
)
```

### STDIO Communicator

```python
from simple_mas.communication.mcp import McpStdioCommunicator

communicator = McpStdioCommunicator(
    agent_name="my_agent",
    service_urls={},
    server_mode=True
)
```
