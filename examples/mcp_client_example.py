#!/usr/bin/env python3
"""Example MCP client implementation.

This example shows how to create an MCP client that connects to
the MCP server and uses its tools, prompts, and resources.

To run:
    poetry run python examples/mcp_client_example.py
"""
import asyncio
import json
import logging

from simple_mas.config import AgentConfig
from simple_mas.logging import configure_logging
from simple_mas.mcp_agent import McpAgent

# Configure logging
configure_logging(level=logging.DEBUG)


class MathClient(McpAgent):
    """Example client that connects to the MCP math server."""

    def __init__(self):
        """Initialize the client agent."""
        config = AgentConfig(name="math_client")
        super().__init__(config=config)


async def run_client():
    """Run the client and interact with the MCP server."""
    client = MathClient()

    try:
        # Connect to the server
        await client.connect_to_service("math", "localhost", 8000)
        print("Connected to math service")

        # List available tools
        tools = await client.list_tools("math")
        print("\nAvailable tools:")
        for tool in tools:
            print(f"- {tool['name']}: {tool['description']}")

        # List available prompts
        prompts = await client.list_prompts("math")
        print("\nAvailable prompts:")
        for prompt in prompts:
            print(f"- {prompt['name']}: {prompt['description']}")

        # List available resources
        resources = await client.list_resources("math")
        print("\nAvailable resources:")
        for resource in resources:
            print(f"- {resource['name']}: {resource['description']}")

        # Use the add tool
        print("\nCalling add tool...")
        add_result = await client.call_tool("math", "add", {"a": 5, "b": 3})
        print(f"5 + 3 = {add_result['result']} (Operation: {add_result['operation']})")

        # Use the multiply tool
        print("\nCalling multiply tool...")
        multiply_result = await client.call_tool("math", "multiply", {"a": 4, "b": 7})
        print(f"4 * 7 = {multiply_result['result']} (Operation: {multiply_result['operation']})")

        # Get weather information
        print("\nGetting weather information...")
        weather = await client.call_tool("math", "get_weather", {"location": "London", "units": "fahrenheit"})
        print(
            f"Weather in {weather['location']}: {weather['temperature']}°"
            f"{weather['units'][0].upper()} ({weather['condition']})"
        )

        # Store a value
        print("\nStoring value in memory...")
        store_result = await client.call_tool("math", "store", {"key": "favorite_color", "value": "blue"})
        print(f"Store result: {store_result['status']}")

        # Retrieve the value
        print("\nRetrieving value from memory...")
        retrieve_result = await client.call_tool("math", "retrieve", {"key": "favorite_color"})
        print(f"Retrieved: {retrieve_result['value']} (Age: {retrieve_result['age_seconds']} seconds)")

        # Try retrieving a non-existent key
        print("\nTrying to retrieve non-existent key...")
        try:
            missing_result = await client.call_tool("math", "retrieve", {"key": "non_existent"})
            print(f"Result: {missing_result['message']}")
        except Exception as e:
            print(f"Error: {e}")

        # Get the greeting prompt
        print("\nGetting greeting prompt...")
        greeting = await client.get_prompt("math", "greeting", {"name": "Math Client"})
        print(f"Greeting: {greeting}")

        # Get the help prompt
        print("\nGetting help prompt...")
        help_text = await client.get_prompt("math", "help")
        print(f"Help:\n{help_text}")

        # Get the info resource
        print("\nGetting info resource...")
        info = await client.get_resource("math", "info")
        info_dict = json.loads(info)
        print("Server info:")
        for key, value in info_dict.items():
            print(f"  {key}: {value}")

        # Get the uptime resource
        print("\nGetting uptime resource...")
        uptime = await client.get_resource("math", "uptime")
        print(f"Server uptime: {uptime.decode('utf-8')}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Disconnect from the service
        await client.disconnect_from_service("math")
        print("\nDisconnected from math service")

        # Stop the client
        await client.stop()


if __name__ == "__main__":
    asyncio.run(run_client())
