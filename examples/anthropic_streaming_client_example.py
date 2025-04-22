#!/usr/bin/env python
"""MCP Streaming Client Example with Anthropic's Python SDK.

This example demonstrates how to use Anthropic's python-sdk to create
a streaming MCP client with Server-Sent Events (SSE). It connects to
the mcp_math_server.py server and makes streaming prompt calls.

The example assumes you have installed the Anthropic python-sdk:
    poetry add anthropic==1.6.0
"""

import asyncio
import logging
import sys
from typing import Any, Dict

# Import from Anthropic's Python SDK (requires anthropic==1.6.0)
try:
    from anthropic.mcp.client.session import ClientSession
    from anthropic.mcp.client.sse import sse_client
    from anthropic.mcp.types import TextContent
except ImportError:
    print("Error: This example requires the Anthropic Python SDK v1.6.0 or later.")
    print("Please install it with: poetry add anthropic==1.6.0")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_streaming_client")


async def stream_prompt(session: ClientSession, prompt_name: str, parameters: Dict[str, Any]) -> None:
    """
    Stream a prompt and display chunks as they arrive.

    Args:
        session: MCP client session
        prompt_name: Name of the prompt to call
        parameters: Parameters to pass to the prompt
    """
    logger.info(f"Streaming prompt: {prompt_name} with parameters: {parameters}")
    print(f"\nStreaming prompt '{prompt_name}':")
    print("-" * 40)

    # Initialize an empty response
    full_response = ""

    # Stream the prompt
    async for chunk in session.stream_prompt(prompt_name, parameters):
        # Process each chunk
        if isinstance(chunk, TextContent):
            # Display the new content
            print(chunk.text, end="", flush=True)
            full_response += chunk.text

    print("\n" + "-" * 40)
    logger.info(f"Full response from {prompt_name}: {full_response}")


async def solve_quadratic_equation(session: ClientSession) -> None:
    """
    Solve a quadratic equation using the MCP prompt with streaming.

    Args:
        session: MCP client session
    """
    logger.info("Solving quadratic equation with streaming")

    # Example: x² - 3x + 2 = 0
    a, b, c = 1, -3, 2

    await stream_prompt(session, "quadratic_equation", {"a": a, "b": b, "c": c})


async def run_streaming_example() -> None:
    """Run the streaming client example."""
    logger.info("Starting MCP streaming client example")

    # MCP server endpoint
    server_url = "http://localhost:8000"

    # Connect to the MCP server
    try:
        logger.info(f"Connecting to MCP server at {server_url}")
        async with sse_client(server_url) as session:
            logger.info("Connected successfully to MCP server")

            # List available tools, prompts, and resources
            tools = await session.list_tools()
            logger.info(f"Available tools: {', '.join(tools)}")

            prompts = await session.list_prompts()
            logger.info(f"Available prompts: {', '.join(prompts)}")

            resources = await session.list_resources()
            logger.info(f"Available resources: {', '.join(resources)}")

            # Example 1: Stream a greeting prompt
            await stream_prompt(session, "greeting", {"name": "Streaming MCP Client"})

            # Example 2: Calculate the area of a circle
            await stream_prompt(session, "circle_area", {"radius": 5.0})

            # Example 3: Solve a quadratic equation
            await solve_quadratic_equation(session)

            logger.info("Streaming client example completed successfully")

    except ConnectionRefusedError:
        logger.error(f"Failed to connect to MCP server at {server_url}")
        print(f"Error: Could not connect to MCP server at {server_url}")
        print("Make sure the server is running (use mcp_math_server.py)")
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        print(f"Error: {e}")


def main() -> int:
    """Main entry point for the example."""
    try:
        asyncio.run(run_streaming_example())
        return 0
    except KeyboardInterrupt:
        logger.info("Client terminated by user")
        print("Client terminated by user")
        return 0
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
