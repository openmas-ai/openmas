#!/usr/bin/env python
"""MCP Client Example with Anthropic's Python SDK.

This example demonstrates how to use Anthropic's python-sdk to create
a non-streaming MCP client. It connects to the mcp_math_server.py
server and makes basic tool, prompt, and resource calls.

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
except ImportError:
    print("Error: This example requires the Anthropic Python SDK v1.6.0 or later.")
    print("Please install it with: poetry add anthropic==1.6.0")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_client")


async def call_prompt(session: ClientSession, prompt_name: str, parameters: Dict[str, Any]) -> None:
    """
    Call a prompt and display the result.

    Args:
        session: MCP client session
        prompt_name: Name of the prompt to call
        parameters: Parameters to pass to the prompt
    """
    logger.info(f"Calling prompt: {prompt_name} with parameters: {parameters}")

    # Call the prompt
    response = await session.call_prompt(prompt_name, parameters)
    logger.info(f"Prompt response: {response}")
    print(f"Prompt '{prompt_name}' response: {response}")


async def run_basic_math_operations(session: ClientSession) -> None:
    """
    Run basic math operations using the MCP tools.

    Args:
        session: MCP client session
    """
    logger.info("Running basic math operations")

    # Addition
    add_result = await session.call_tool("add", {"a": 5, "b": 3})
    logger.info(f"5 + 3 = {add_result.value}")
    print(f"Addition: 5 + 3 = {add_result.value}")

    # Subtraction
    sub_result = await session.call_tool("subtract", {"a": 10, "b": 4})
    logger.info(f"10 - 4 = {sub_result.value}")
    print(f"Subtraction: 10 - 4 = {sub_result.value}")

    # Multiplication
    mul_result = await session.call_tool("multiply", {"a": 6, "b": 7})
    logger.info(f"6 * 7 = {mul_result.value}")
    print(f"Multiplication: 6 * 7 = {mul_result.value}")

    # Division
    div_result = await session.call_tool("divide", {"a": 20, "b": 4})
    logger.info(f"20 / 4 = {div_result.value}")
    print(f"Division: 20 / 4 = {div_result.value}")

    # Square root
    sqrt_result = await session.call_tool("sqrt", {"x": 16})
    logger.info(f"√16 = {sqrt_result.value}")
    print(f"Square root: √16 = {sqrt_result.value}")

    # Power
    power_result = await session.call_tool("power", {"base": 2, "exponent": 3})
    logger.info(f"2^3 = {power_result.value}")
    print(f"Power: 2^3 = {power_result.value}")


async def test_storage(session: ClientSession) -> None:
    """
    Test the storage and retrieval capabilities.

    Args:
        session: MCP client session
    """
    logger.info("Testing storage functionality")

    # Store a value
    key = "test_key"
    value = "test_value"
    store_result = await session.call_tool("store", {"key": key, "value": value})
    logger.info(f"Stored {key}={value}: {store_result.value}")
    print(f"Stored: {key}={value}")

    # Retrieve the value
    retrieve_result = await session.call_tool("retrieve", {"key": key})
    logger.info(f"Retrieved {key}={retrieve_result.value}")
    print(f"Retrieved: {key}={retrieve_result.value}")


async def access_resources(session: ClientSession) -> None:
    """
    Access and display the available resources.

    Args:
        session: MCP client session
    """
    logger.info("Accessing MCP resources")

    # Get Pi value
    pi_resource = await session.get_resource("pi")
    logger.info(f"Pi value: {pi_resource}")
    print(f"Pi value: {pi_resource}")

    # Get Euler's number
    e_resource = await session.get_resource("e")
    logger.info(f"Euler's number value: {e_resource}")
    print(f"Euler's number value: {e_resource}")


async def get_weather_info(session: ClientSession) -> None:
    """
    Get weather information for a city.

    Args:
        session: MCP client session
    """
    logger.info("Getting weather information")

    cities = ["New York", "London", "Tokyo", "Sydney"]

    for city in cities:
        try:
            weather_result = await session.call_tool("get_weather", {"city": city})
            logger.info(f"Weather in {city}: {weather_result.value}")
            print(f"Weather in {city}: {weather_result.value}")
        except Exception as e:
            logger.error(f"Failed to get weather for {city}: {e}")
            print(f"Failed to get weather for {city}: {e}")


async def run_client_example() -> None:
    """Run the client example."""
    logger.info("Starting MCP client example")

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

            # Example 1: Run basic math operations
            print("\n=== Basic Math Operations ===")
            await run_basic_math_operations(session)

            # Example 2: Call prompts
            print("\n=== Calling Prompts ===")
            await call_prompt(session, "greeting", {"name": "MCP Client"})
            await call_prompt(session, "circle_area", {"radius": 3.0})
            await call_prompt(session, "quadratic_equation", {"a": 1, "b": -3, "c": 2})

            # Example 3: Access resources
            print("\n=== Accessing Resources ===")
            await access_resources(session)

            # Example 4: Test storage functionality
            print("\n=== Testing Storage ===")
            await test_storage(session)

            # Example 5: Weather information
            print("\n=== Weather Information ===")
            await get_weather_info(session)

            logger.info("Client example completed successfully")

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
        asyncio.run(run_client_example())
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
