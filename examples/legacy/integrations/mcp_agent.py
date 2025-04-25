#!/usr/bin/env python3
"""Example of a Simple MCP-enabled agent using the latest MCP SDK patterns.

This example demonstrates:
1. Creating an MCP agent with tools and prompts
2. Implementing several tool handlers
3. Setting up an MCP server
4. Running the agent with a FastMCP server

Requirements:
- mcp package (install via: poetry add mcp)
- anthropic package (install via: poetry add anthropic)

To run this example:
$ poetry run python examples/integrations/mcp_agent.py
"""

import asyncio
import datetime
import logging
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Type, TypeVar, cast

# Type variables for the MCP types
TextContentT = TypeVar("TextContentT")
CallToolResultT = TypeVar("CallToolResultT")
FastMCPT = TypeVar("FastMCPT")
ContextT = TypeVar("ContextT")
ClientSessionT = TypeVar("ClientSessionT")

# Try to import MCP packages
try:
    # Import the real types
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client
    from mcp.server.fastmcp import Context, FastMCP
    from mcp.types import CallToolResult, TextContent

    HAS_MCP = True
except ImportError:
    # Define stub types for when MCP is not installed
    HAS_MCP = False
    logging.warning("MCP package not installed. This example will not run.")

    # Define stubs only if the imports failed
    # flake8: noqa
    class TextContent:  # type: ignore
        """Stub class for TextContent when MCP is not installed."""

        def __init__(self, text: str, type: str) -> None:
            self.text = text
            self.type = type

    class CallToolResult:  # type: ignore
        """Stub class for CallToolResult when MCP is not installed."""

        def __init__(self, **kwargs: Any) -> None:
            pass

    class FastMCP:  # type: ignore
        """Stub class for FastMCP when MCP is not installed."""

        def __init__(self, title: str) -> None:
            self.title = title

        def tool(self, name: str) -> Callable[[Callable], Callable]:
            def decorator(func: Callable) -> Callable:
                return func

            return decorator

        def prompt(self, name: str) -> Callable[[Callable], Callable]:
            def decorator(func: Callable) -> Callable:
                return func

            return decorator

        def resource(self, name: str) -> Callable[[Callable], Callable]:
            def decorator(func: Callable) -> Callable:
                return func

            return decorator

        async def serve(self, host: str, port: int) -> None:
            """Stub for serve method."""
            print(f"Pretend server running at {host}:{port}")
            await asyncio.sleep(3600)  # Pretend to run forever

    class Context:  # type: ignore
        """Stub class for Context when MCP is not installed."""

        pass

    class ClientSession:  # type: ignore
        """Stub class for ClientSession when MCP is not installed."""

        pass

    # Stub function for stdio_client
    async def stdio_client(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:  # type: ignore
        """Stub for stdio_client function."""
        if False:  # This code won't actually run
            yield None


from openmas.agent.mcp import McpAgent  # noqa: E402
from openmas.communication import BaseCommunicator, HttpCommunicator  # noqa: E402
from openmas.config import AgentConfig  # noqa: E402


class AssistantAgent(McpAgent):
    """An agent that can perform calculations and get weather information."""

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[AgentConfig] = None,
        communicator_class: Optional[Type[BaseCommunicator]] = None,
    ):
        """Initialize the agent.

        Args:
            name: The name of the agent
            config: The agent configuration
            communicator_class: The communicator class to use
        """
        # Convert AgentConfig to dict if provided
        config_dict = {}
        if config:
            config_dict = config.model_dump()

        # Ensure name is in the config dict
        config_dict["name"] = name or (config.name if config else "assistant-agent")

        # Call the parent constructor with the determined parameters
        super().__init__(name=name, config=config_dict, communicator_class=communicator_class or HttpCommunicator)
        # Initialize request tracking attributes
        self.request_count = 0
        self.last_request_time: Optional[datetime.datetime] = None

    async def get_weather(self, location: str, unit: str = "celsius") -> Dict[str, Any]:
        """Get weather for a location.

        Args:
            location: The location to get weather for
            unit: Temperature unit (celsius or fahrenheit)

        Returns:
            Dict containing weather information
        """
        # Track request
        self.request_count += 1
        self.last_request_time = datetime.datetime.now()

        # Simulate weather data (in a real agent, this would call a weather API)
        self.logger.info(f"Getting weather for {location} in {unit}")

        # Simulated weather data
        temperature = 22 if unit.lower() == "celsius" else 72

        return {
            "location": location,
            "temperature": temperature,
            "unit": unit.lower(),
            "condition": "sunny",
            "humidity": 65,
            "requested_at": self.last_request_time.isoformat(),
        }

    async def calculate(self, operation: str, numbers: List[float]) -> Dict[str, Any]:
        """Perform calculations on a list of numbers.

        Args:
            operation: The operation to perform (sum, average, min, max)
            numbers: List of numbers to operate on

        Returns:
            Dict containing the result of the calculation
        """
        # Track request
        self.request_count += 1
        self.last_request_time = datetime.datetime.now()

        self.logger.info(f"Performing {operation} on {numbers}")

        # Perform the requested calculation
        if operation == "sum":
            result = sum(numbers)
        elif operation == "average":
            result = sum(numbers) / len(numbers)
        elif operation == "min":
            result = min(numbers)
        elif operation == "max":
            result = max(numbers)
        else:
            return {"error": f"Unsupported operation: {operation}"}

        return {
            "operation": operation,
            "numbers": numbers,
            "result": result,
        }

    async def get_agent_status(self) -> Dict[str, Any]:
        """Get the current status of the agent.

        Returns:
            Dict containing agent status information
        """
        # Return agent status information
        return {
            "name": self.name,
            "request_count": self.request_count,
            "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
            "status": "running",
        }

    async def assistant_prompt(self, query: str) -> TextContent:
        """Handle general assistant prompt requests.

        Args:
            query: The user's query

        Returns:
            TextContent with assistant response
        """
        # Track request
        self.request_count += 1
        self.last_request_time = datetime.datetime.now()

        self.logger.info(f"Assistant prompt received: {query}")

        # Generate a response (in a real agent, this would use an LLM)
        response = f"""
You asked: "{query}"

I'm a simple MCP assistant agent. For specific functionality, please use my tools:
- get_weather: Get weather information for a location
- calculate: Perform calculations on a list of numbers
- get_agent_status: Check my current status
        """

        return TextContent(text=response, type="text")

    async def help_resource(self) -> Dict[str, Any]:
        """Provide help information about the agent's capabilities.

        Returns:
            Dict containing help information about the agent
        """
        return {
            "agent_name": self.name,
            "description": "An example MCP-enabled assistant agent with tools and prompts",
            "tools": [
                {
                    "name": "get_weather",
                    "description": "Get weather for a location",
                    "parameters": {
                        "location": "The location to get weather for",
                        "unit": "Temperature unit (celsius or fahrenheit, optional)",
                    },
                },
                {
                    "name": "calculate",
                    "description": "Perform calculations on a list of numbers",
                    "parameters": {
                        "operation": "The operation to perform (sum, average, min, max)",
                        "numbers": "List of numbers to operate on",
                    },
                },
                {"name": "get_agent_status", "description": "Get the current status of the agent", "parameters": {}},
            ],
            "prompts": [{"name": "assistant", "description": "General assistant prompt handler"}],
            "resources": [{"name": "help", "description": "Get help information about the agent's capabilities"}],
        }


async def create_mcp_server(agent: AssistantAgent, port: int = 8000) -> None:
    """Create and start an MCP server for the agent.

    Args:
        agent: The agent to expose via MCP
        port: The port to run the server on
    """
    if not HAS_MCP:
        logging.error("Cannot create MCP server: MCP package not installed")
        return

    # Create FastMCP server
    server = FastMCP(title=f"{agent.name} MCP API")

    # Register tools
    server.tool("get_weather")(agent.get_weather)
    server.tool("calculate")(agent.calculate)
    server.tool("get_agent_status")(agent.get_agent_status)

    # Register prompts
    server.prompt("assistant")(agent.assistant_prompt)

    # Register resources
    server.resource("help")(agent.help_resource)

    # Start the server
    logging.info(f"Starting MCP server on port {port}")
    # For type checking only - check if serve method exists
    if hasattr(server, "serve"):
        await server.serve(host="0.0.0.0", port=port)
    else:
        logging.error("FastMCP does not have a serve method")


async def main() -> None:
    """Run the example."""
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Check if MCP is installed
    if not HAS_MCP:
        logging.error("MCP package not installed. Please install it with 'poetry add mcp'")
        return

    # Create agent config
    config = AgentConfig(
        name="mcp-example-agent",
        log_level="INFO",
        communicator_type="in-memory",
        service_urls={},
    )

    # Create agent
    agent = AssistantAgent(config=config)

    try:
        # Start MCP server
        await create_mcp_server(agent)
    except KeyboardInterrupt:
        logging.info("Shutting down MCP server")


if __name__ == "__main__":
    asyncio.run(main())
