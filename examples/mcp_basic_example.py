#!/usr/bin/env python
"""Basic MCP example using Python's FastMCP library.

This example demonstrates a simple MCP server and client using FastMCP,
which is a library for implementing the Model Context Protocol.

To run:
    poetry run python examples/mcp_basic_example.py
"""
import asyncio
import logging
import sys
from typing import Any, Dict, List

from mcp.client.session import ClientSession
from mcp.messages import Message, MessageRole, TextContent
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import TextContent as ResponseTextContent

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# === SERVER IMPLEMENTATION ===

# Initialize the MCP server
mcp = FastMCP(name="MathServer", instructions="A simple math server that provides basic arithmetic operations.")


# Define tools using decorators
@mcp.tool(description="Add two numbers together")
async def add(a: float, b: float, ctx: Context) -> Dict[str, Any]:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number
        ctx: MCP context

    Returns:
        Result of the addition
    """
    result = a + b
    logger.info(f"Adding {a} + {b} = {result}")
    await ctx.info(f"Calculated: {a} + {b}")
    return {"result": result}


@mcp.tool(description="Multiply two numbers")
async def multiply(a: float, b: float, ctx: Context) -> Dict[str, Any]:
    """Multiply two numbers.

    Args:
        a: First number
        b: Second number
        ctx: MCP context

    Returns:
        Result of the multiplication
    """
    result = a * b
    logger.info(f"Multiplying {a} * {b} = {result}")
    await ctx.info(f"Calculated: {a} * {b}")
    return {"result": result}


# Define a prompt using decorators
@mcp.prompt(description="Generate a greeting")
async def greeting_prompt(name: str) -> List[Message]:
    """Generate a greeting for the given name.

    Args:
        name: Name to greet

    Returns:
        List of messages for the prompt
    """
    logger.info(f"Creating greeting prompt for: {name}")

    system_message = Message(role=MessageRole.SYSTEM, content=[TextContent(text="You are a helpful assistant.")])

    user_message = Message(
        role=MessageRole.USER, content=[TextContent(text=f"Generate a friendly greeting for {name}.")]
    )

    return [system_message, user_message]


# Define a resource using decorators
@mcp.resource("resource://pi", name="Pi Value", description="Value of Pi")
async def pi_resource() -> str:
    """Return the value of Pi.

    Returns:
        Value of Pi as a string
    """
    import math

    logger.info("Accessing Pi resource")
    return str(math.pi)


# === CLIENT IMPLEMENTATION ===


async def run_client():
    """Run the MCP client."""
    logger.info("Starting MCP client")

    # Connect to the server
    base_url = "http://localhost:8000"

    # Create a client session
    session = ClientSession(base_url)
    await session.initialize()

    try:
        logger.info(f"Connected to MCP server at {base_url}")

        # List available tools
        logger.info("\n=== Available Tools ===")
        tools = await session.list_tools()
        for tool in tools:
            logger.info(f"Tool: {tool.name} - {tool.description}")

        # List available prompts
        logger.info("\n=== Available Prompts ===")
        prompts = await session.list_prompts()
        for prompt in prompts:
            logger.info(f"Prompt: {prompt.name} - {prompt.description}")

        # List available resources
        logger.info("\n=== Available Resources ===")
        resources = await session.list_resources()
        for resource in resources:
            logger.info(f"Resource: {resource.name} - {resource.description}")

        # Call add tool
        logger.info("\n=== Calling 'add' tool ===")
        add_result = await session.call_tool("add", {"a": 5, "b": 3})
        logger.info(f"5 + 3 = {add_result.value['result']}")

        # Call multiply tool
        logger.info("\n=== Calling 'multiply' tool ===")
        multiply_result = await session.call_tool("multiply", {"a": 4, "b": 7})
        logger.info(f"4 * 7 = {multiply_result.value['result']}")

        # Get greeting prompt
        logger.info("\n=== Getting 'greeting_prompt' ===")
        greeting = await session.call_prompt("greeting_prompt", {"name": "MCP User"})
        if isinstance(greeting, ResponseTextContent):
            logger.info(f"Greeting: {greeting.text}")

        # Get pi resource
        logger.info("\n=== Getting 'pi' resource ===")
        pi_value = await session.get_resource("resource://pi")
        logger.info(f"Pi = {pi_value}")

    finally:
        # Close the session
        await session.close()
        logger.info("Client session closed")


async def main():
    """Run the example as a server."""
    port = 8000
    logger.info(f"Starting MCP server on port {port}")

    # Start the server
    server_task = asyncio.create_task(mcp.serve_http(port=port))

    # Give the server a moment to start
    await asyncio.sleep(2)

    try:
        # Run the client
        await run_client()
    finally:
        # Stop the server
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        logger.info("Server stopped")


if __name__ == "__main__":
    # Check if running as a client or server
    if len(sys.argv) > 1 and sys.argv[1] == "client":
        # Run as client only
        asyncio.run(run_client())
    else:
        # Run full example (server + client)
        asyncio.run(main())
