#!/usr/bin/env python3
"""Example MCP server agent implementation.

This example shows how to create an MCP server agent that provides
tools, prompts, and resources to clients.

To run:
    poetry run python examples/mcp_server_example.py
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional

from pydantic import BaseModel

from simple_mas.config import AgentConfig
from simple_mas.logging import configure_logging
from simple_mas.mcp_agent import McpServerAgent, mcp_prompt, mcp_resource, mcp_tool

# Configure logging
configure_logging(level=logging.DEBUG)


# Pydantic models for request and response
class AddRequest(BaseModel):
    """Request model for the add tool."""

    a: int
    b: int


class MultiplyRequest(BaseModel):
    """Request model for the multiply tool."""

    a: int
    b: int


class CalculationResult(BaseModel):
    """Response model for calculation tools."""

    result: int
    operation: str


class WeatherRequest(BaseModel):
    """Request model for the weather tool."""

    location: str
    units: Optional[str] = "celsius"


class WeatherResponse(BaseModel):
    """Response model for the weather tool."""

    temperature: float
    condition: str
    location: str
    units: str


@dataclass
class MemoryEntry:
    """Data model for a single memory entry."""

    value: str
    created_at: float


class MathAgent(McpServerAgent):
    """Example MCP server agent that provides math and utility tools."""

    def __init__(self, **kwargs):
        """Initialize the math agent."""
        config = AgentConfig(name="math_agent")
        super().__init__(config=config, **kwargs)

        # Initialize memory store
        self._memory: Dict[str, MemoryEntry] = {}
        self._creation_time = asyncio.get_event_loop().time()

    @mcp_tool(description="Add two numbers together")
    def add(self, a: int, b: int) -> CalculationResult:
        """Add two numbers and return the result.

        Args:
            a: First number.
            b: Second number.

        Returns:
            Result of the addition.
        """
        result = a + b
        return CalculationResult(result=result, operation="add")

    @mcp_tool(description="Multiply two numbers")
    def multiply(self, a: int, b: int) -> CalculationResult:
        """Multiply two numbers and return the result.

        Args:
            a: First number.
            b: Second number.

        Returns:
            Result of the multiplication.
        """
        result = a * b
        return CalculationResult(result=result, operation="multiply")

    @mcp_tool(name="get_weather", description="Get weather information for a location")
    async def get_weather(self, location: str, units: str = "celsius") -> WeatherResponse:
        """Get weather information for a location.

        Args:
            location: Name of the location.
            units: Temperature units ("celsius" or "fahrenheit").

        Returns:
            Weather information.
        """
        # Simulate API call with delay
        await asyncio.sleep(0.5)

        # Generate fake weather data
        weather_data = {
            "New York": (25, "Sunny"),
            "London": (18, "Cloudy"),
            "Tokyo": (28, "Rainy"),
            "Sydney": (22, "Clear"),
        }

        if location not in weather_data:
            default_temp = 20
            default_condition = "Unknown"
        else:
            default_temp, default_condition = weather_data[location]

        # Convert temperature if needed
        temp = default_temp
        if units.lower() == "fahrenheit":
            temp = temp * 9 / 5 + 32

        return WeatherResponse(temperature=temp, condition=default_condition, location=location, units=units)

    @mcp_tool(description="Store a value in memory")
    def store(self, key: str, value: str) -> Dict[str, str]:
        """Store a value in memory.

        Args:
            key: Memory key.
            value: Value to store.

        Returns:
            Status information.
        """
        self._memory[key] = MemoryEntry(value=value, created_at=asyncio.get_event_loop().time())
        return {"status": "success", "key": key}

    @mcp_tool(description="Retrieve a value from memory")
    def retrieve(self, key: str) -> Dict[str, str]:
        """Retrieve a value from memory.

        Args:
            key: Memory key.

        Returns:
            Stored value or error message.
        """
        if key not in self._memory:
            return {"status": "error", "message": f"Key '{key}' not found"}

        entry = self._memory[key]
        age = asyncio.get_event_loop().time() - entry.created_at

        return {"status": "success", "key": key, "value": entry.value, "age_seconds": round(age, 2)}

    @mcp_prompt(name="greeting", description="Get a greeting message")
    def get_greeting(self, name: str = "User") -> str:
        """Generate a greeting message.

        Args:
            name: Name to include in the greeting.

        Returns:
            Greeting message.
        """
        return f"Hello, {name}! Welcome to the Math Agent service."

    @mcp_prompt(name="help", description="Get help text for using the agent")
    def get_help(self) -> str:
        """Generate help text.

        Returns:
            Help text.
        """
        return """
        Math Agent provides the following services:

        Tools:
        - add: Add two numbers together
        - multiply: Multiply two numbers
        - get_weather: Get weather information for a location
        - store: Store a value in memory
        - retrieve: Retrieve a value from memory

        Prompts:
        - greeting: Get a greeting message
        - help: Get this help text

        Resources:
        - info: Get information about the agent
        - uptime: Get agent uptime information
        """

    @mcp_resource(name="info", description="Get information about the agent")
    def get_info(self) -> str:
        """Get agent information.

        Returns:
            Agent information in JSON format.
        """
        import json

        info = {
            "name": self.config.name,
            "type": "Math Agent",
            "version": "1.0.0",
            "tools": len(self._tools),
            "prompts": len(self._prompts),
            "resources": len(self._resources),
            "memory_entries": len(self._memory),
        }

        return json.dumps(info, indent=2)

    @mcp_resource(name="uptime", description="Get agent uptime information")
    def get_uptime(self) -> bytes:
        """Get agent uptime.

        Returns:
            Uptime information.
        """
        uptime_seconds = asyncio.get_event_loop().time() - self._creation_time
        minutes, seconds = divmod(uptime_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        uptime_str = f"Uptime: {int(hours)}h {int(minutes)}m {int(seconds)}s"
        return uptime_str.encode("utf-8")


async def main():
    """Run the MCP server agent."""
    # Create and start the agent
    agent = MathAgent(mcp_host="localhost", mcp_port=8000)

    try:
        await agent.start()
        print(f"MCP server agent '{agent.config.name}' started on localhost:8000")
        print("Press Ctrl+C to stop the server...")

        # Keep the server running
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await agent.stop()
        print("Server stopped.")


if __name__ == "__main__":
    asyncio.run(main())
