#!/usr/bin/env python
"""
Mock MCP (Model Context Protocol) Example.

This script demonstrates the concepts of MCP using mock implementations of
client and server classes. This is useful for understanding the architecture
without requiring the actual MCP library.
"""

import asyncio
import json
import logging
import math
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_mock")


# ====== Mock MCP Classes ======


@dataclass
class Tool:
    """Represents an MCP tool."""

    name: str
    description: str
    function: Callable


@dataclass
class Prompt:
    """Represents an MCP prompt."""

    name: str
    description: str
    function: Callable


@dataclass
class Resource:
    """Represents an MCP resource."""

    name: str
    description: str
    mime_type: str
    function: Callable


class MockMcpServer:
    """Mock implementation of an MCP server."""

    def __init__(self, name: str, instructions: str = ""):
        """Initialize the mock MCP server.

        Args:
            name: Server name
            instructions: Server instructions
        """
        self.name = name
        self.instructions = instructions
        self.tools: Dict[str, Tool] = {}
        self.prompts: Dict[str, Prompt] = {}
        self.resources: Dict[str, Resource] = {}
        self.running = False
        logger.info(f"Created MockMcpServer '{name}'")

    def register_tool(self, name: str, function: Callable, description: str) -> None:
        """Register a tool with the server.

        Args:
            name: Tool name
            function: Tool implementation
            description: Tool description
        """
        self.tools[name] = Tool(name, description, function)
        logger.info(f"Registered tool '{name}': {description}")

    def register_prompt(self, name: str, function: Callable, description: str) -> None:
        """Register a prompt with the server.

        Args:
            name: Prompt name
            function: Prompt implementation
            description: Prompt description
        """
        self.prompts[name] = Prompt(name, description, function)
        logger.info(f"Registered prompt '{name}': {description}")

    def register_resource(self, name: str, function: Callable, mime_type: str, description: str) -> None:
        """Register a resource with the server.

        Args:
            name: Resource name
            function: Resource implementation
            mime_type: MIME type of the resource
            description: Resource description
        """
        self.resources[name] = Resource(name, description, mime_type, function)
        logger.info(f"Registered resource '{name}': {description}")

    async def start(self, port: int = 8000) -> None:
        """Start the server on the specified port.

        Args:
            port: Port to listen on
        """
        self.running = True
        logger.info(f"Started MockMcpServer '{self.name}' on port {port}")

    async def stop(self) -> None:
        """Stop the server."""
        self.running = False
        logger.info(f"Stopped MockMcpServer '{self.name}'")

    async def call_tool(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the server.

        Args:
            name: Tool name
            params: Tool parameters

        Returns:
            Tool result

        Raises:
            KeyError: If tool doesn't exist
        """
        if name not in self.tools:
            raise KeyError(f"Tool '{name}' not found")

        tool = self.tools[name]
        logger.info(f"Server processing tool call: {name}({json.dumps(params)})")
        result = await tool.function(**params)
        return result

    async def get_prompt(self, name: str, params: Dict[str, Any]) -> str:
        """Get a prompt from the server.

        Args:
            name: Prompt name
            params: Prompt parameters

        Returns:
            Prompt text

        Raises:
            KeyError: If prompt doesn't exist
        """
        if name not in self.prompts:
            raise KeyError(f"Prompt '{name}' not found")

        prompt = self.prompts[name]
        logger.info(f"Server processing prompt request: {name}({json.dumps(params)})")
        result = await prompt.function(**params)
        return result

    async def get_resource(self, name: str) -> bytes:
        """Get a resource from the server.

        Args:
            name: Resource name

        Returns:
            Resource content

        Raises:
            KeyError: If resource doesn't exist
        """
        if name not in self.resources:
            raise KeyError(f"Resource '{name}' not found")

        resource = self.resources[name]
        logger.info(f"Server processing resource request: {name}")
        result = await resource.function()
        return result


class MockMcpClient:
    """Mock implementation of an MCP client."""

    def __init__(self, server: MockMcpServer):
        """Initialize the mock MCP client.

        Args:
            server: Server to connect to
        """
        self.server = server
        self.connected = False
        logger.info("Created MockMcpClient")

    async def connect(self) -> None:
        """Connect to the server."""
        self.connected = True
        logger.info(f"Connected to server '{self.server.name}'")

    async def disconnect(self) -> None:
        """Disconnect from the server."""
        self.connected = False
        logger.info("Disconnected from server")

    async def list_tools(self) -> List[Dict[str, str]]:
        """List available tools.

        Returns:
            List of tool information
        """
        logger.info("Client listing tools")
        return [{"name": name, "description": tool.description} for name, tool in self.server.tools.items()]

    async def list_prompts(self) -> List[Dict[str, str]]:
        """List available prompts.

        Returns:
            List of prompt information
        """
        logger.info("Client listing prompts")
        return [{"name": name, "description": prompt.description} for name, prompt in self.server.prompts.items()]

    async def list_resources(self) -> List[Dict[str, str]]:
        """List available resources.

        Returns:
            List of resource information
        """
        logger.info("Client listing resources")
        return [{"name": name, "description": resource.description} for name, resource in self.server.resources.items()]

    async def call_tool(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the server.

        Args:
            name: Tool name
            params: Tool parameters

        Returns:
            Tool result
        """
        logger.info(f"Client calling tool: {name}({json.dumps(params)})")
        return await self.server.call_tool(name, params)

    async def get_prompt(self, name: str, params: Dict[str, Any]) -> str:
        """Get a prompt from the server.

        Args:
            name: Prompt name
            params: Prompt parameters

        Returns:
            Prompt text
        """
        logger.info(f"Client requesting prompt: {name}({json.dumps(params)})")
        return await self.server.get_prompt(name, params)

    async def get_resource(self, name: str) -> bytes:
        """Get a resource from the server.

        Args:
            name: Resource name

        Returns:
            Resource content
        """
        logger.info(f"Client requesting resource: {name}")
        return await self.server.get_resource(name)


# ====== Tool, Prompt, and Resource Implementations ======


async def add_tool(a: float, b: float) -> Dict[str, float]:
    """Add two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of the numbers
    """
    result = a + b
    return {"result": result}


async def multiply_tool(a: float, b: float) -> Dict[str, float]:
    """Multiply two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Product of the numbers
    """
    result = a * b
    return {"result": result}


async def greeting_prompt(name: str) -> str:
    """Generate a greeting prompt.

    Args:
        name: Name to greet

    Returns:
        Greeting text
    """
    return f"""
Hello, {name}!

Welcome to the MCP example. This is a sample prompt that demonstrates
how to use prompts in the Model Context Protocol.

You can use this protocol to:
1. Call tools (like add and multiply)
2. Get prompts (like this one)
3. Access resources
"""


async def pi_resource() -> bytes:
    """Get the value of Pi.

    Returns:
        Pi value as bytes
    """
    return str(math.pi).encode("utf-8")


# ====== Example Runner ======


async def run_example():
    """Run the MCP example with mock client and server."""
    # Create and set up server
    server = MockMcpServer("MathServer", "A server for math operations")

    # Register tools
    server.register_tool("add", add_tool, "Add two numbers")
    server.register_tool("multiply", multiply_tool, "Multiply two numbers")

    # Register prompts
    server.register_prompt("greeting", greeting_prompt, "Generate a greeting")

    # Register resources
    server.register_resource("pi", pi_resource, "text/plain", "Value of Pi")

    # Start server
    await server.start()

    # Create and connect client
    client = MockMcpClient(server)
    await client.connect()

    try:
        # List available tools
        tools = await client.list_tools()
        logger.info("Available tools:")
        for tool in tools:
            logger.info(f"  {tool['name']}: {tool['description']}")

        # List available prompts
        prompts = await client.list_prompts()
        logger.info("Available prompts:")
        for prompt in prompts:
            logger.info(f"  {prompt['name']}: {prompt['description']}")

        # List available resources
        resources = await client.list_resources()
        logger.info("Available resources:")
        for resource in resources:
            logger.info(f"  {resource['name']}: {resource['description']}")

        # Call tools
        add_result = await client.call_tool("add", {"a": 5, "b": 3})
        logger.info(f"5 + 3 = {add_result['result']}")

        multiply_result = await client.call_tool("multiply", {"a": 4, "b": 7})
        logger.info(f"4 * 7 = {multiply_result['result']}")

        # Get a prompt
        greeting = await client.get_prompt("greeting", {"name": "User"})
        logger.info(f"Greeting prompt:\n{greeting}")

        # Get a resource
        pi_bytes = await client.get_resource("pi")
        logger.info(f"Pi = {pi_bytes.decode('utf-8')}")

        logger.info("Example completed successfully")
    finally:
        # Disconnect client and stop server
        await client.disconnect()
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_example())
    except KeyboardInterrupt:
        logger.info("Example terminated by user")
        sys.exit(0)
