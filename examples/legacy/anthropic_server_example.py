#!/usr/bin/env python
"""
Basic MCP Server Example with Anthropic's Python SDK.

This example demonstrates how to use Anthropic's python-sdk to create
a FastMCP server that implements tools, prompts, and resources.
It works with the anthropic_client_example.py script.

The example assumes you have installed the Anthropic python-sdk:
    poetry add anthropic==1.6.0
"""

import asyncio
import logging
import math
import sys

# Import from Anthropic's Python SDK (requires anthropic==1.6.0)
try:
    from anthropic.mcp.server.fastmcp import Context, FastMCP
    from anthropic.mcp.types import TextContent
except ImportError:
    print("Error: This example requires the Anthropic Python SDK v1.6.0 or later.")
    print("Please install it with: poetry add anthropic==1.6.0")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_server_example")


class MathServer:
    """MCP server that provides math functions and resources."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        """Initialize the server.

        Args:
            host: Host address to bind the server to
            port: Port number to bind the server to
        """
        self.host = host
        self.port = port
        self.server = FastMCP(host=host, port=port)
        self.setup_tools()
        self.setup_prompts()
        self.setup_resources()
        logger.info(f"MathServer initialized on {host}:{port}")

    def setup_tools(self):
        """Set up the mathematical tools."""

        # Register add tool
        @self.server.tool("add", "Add two numbers together")
        async def add(ctx: Context, a: float, b: float) -> float:
            """Add two numbers together."""
            result = a + b
            logger.info(f"Add: {a} + {b} = {result}")
            return result

        # Register subtract tool
        @self.server.tool("subtract", "Subtract one number from another")
        async def subtract(ctx: Context, a: float, b: float) -> float:
            """Subtract b from a."""
            result = a - b
            logger.info(f"Subtract: {a} - {b} = {result}")
            return result

        # Register multiply tool
        @self.server.tool("multiply", "Multiply two numbers together")
        async def multiply(ctx: Context, a: float, b: float) -> float:
            """Multiply two numbers together."""
            result = a * b
            logger.info(f"Multiply: {a} * {b} = {result}")
            return result

        # Register divide tool
        @self.server.tool("divide", "Divide one number by another")
        async def divide(ctx: Context, a: float, b: float) -> float:
            """Divide a by b."""
            if b == 0:
                raise ValueError("Cannot divide by zero")
            result = a / b
            logger.info(f"Divide: {a} / {b} = {result}")
            return result

        # Register square root tool
        @self.server.tool("sqrt", "Calculate the square root of a number")
        async def sqrt(ctx: Context, x: float) -> float:
            """Calculate the square root of x."""
            if x < 0:
                raise ValueError("Cannot calculate square root of a negative number")
            result = math.sqrt(x)
            logger.info(f"Square root of {x} = {result}")
            return result

    def setup_prompts(self):
        """Set up example prompts."""

        # Register a prompt for calculating circle area
        @self.server.prompt("circle_area", "Calculate the area of a circle")
        async def circle_area(ctx: Context, radius: float) -> TextContent:
            """Calculate the area of a circle with the given radius."""
            area = math.pi * radius * radius
            return TextContent(text=f"The area of a circle with radius {radius} is {area:.4f} square units.")

        # Register a prompt for greeting
        @self.server.prompt("greeting", "Generate a greeting message")
        async def greeting(ctx: Context, name: str = "User") -> TextContent:
            """Generate a greeting message."""
            return TextContent(text=f"Hello, {name}! Welcome to the MCP Math Server.")

    def setup_resources(self):
        """Set up resources."""

        # Register Pi as a resource
        @self.server.resource("pi", "The value of Pi")
        async def pi(ctx: Context) -> float:
            """Return the value of Pi."""
            return math.pi

        # Register Euler's number as a resource
        @self.server.resource("e", "The value of Euler's number")
        async def euler(ctx: Context) -> float:
            """Return the value of Euler's number."""
            return math.e

    async def start(self):
        """Start the MCP server."""
        logger.info(f"Starting MCP Math Server on {self.host}:{self.port}")
        await self.server.start()
        logger.info("MCP Math Server started")

    async def stop(self):
        """Stop the MCP server."""
        logger.info("Stopping MCP Math Server")
        await self.server.stop()
        logger.info("MCP Math Server stopped")


async def main():
    """Main entry point."""
    logger.info("Starting MCP server example")

    # Create and start the server
    server = MathServer(host="0.0.0.0", port=8000)

    try:
        await server.start()

        # Keep the server running until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Server terminated by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return 1
    finally:
        # Ensure the server is properly stopped
        await server.stop()

    logger.info("MCP server example completed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
