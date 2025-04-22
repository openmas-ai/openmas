#!/usr/bin/env python
"""Example MCP agent implementation.

This example demonstrates how to create an MCP agent with tools, prompts, and resources.
It shows how to use the MCP decorators and set up a server that an LLM can connect to.
"""
import asyncio
import logging
import os
from typing import Dict, List, Optional

from pydantic import BaseModel

from simple_mas.agent.mcp import McpAgent, mcp_prompt, mcp_resource, mcp_tool
from simple_mas.communication.mcp.sse_communicator import McpSseCommunicator
from simple_mas.logging import get_logger

logger = get_logger(__name__)


class WeatherResponse(BaseModel):
    """Response model for weather data."""

    temperature: float
    conditions: str
    location: str


class MyMcpAgent(McpAgent):
    """Example MCP agent with tools, prompts, and resources."""

    def __init__(self, name: str):
        """Initialize the agent."""
        super().__init__(name)
        self.data_store = {
            "notes": {},
            "weather": {
                "San Francisco": {"temperature": 68.0, "conditions": "Foggy"},
                "New York": {"temperature": 75.0, "conditions": "Sunny"},
                "London": {"temperature": 60.0, "conditions": "Rainy"},
            },
        }

    @mcp_tool(name="get_weather", description="Get the current weather for a location")
    async def get_weather(self, location: str) -> Dict:
        """Get weather information for a location.

        Args:
            location: The location to get weather for

        Returns:
            Weather information including temperature and conditions
        """
        if location not in self.data_store["weather"]:
            return {"temperature": 70.0, "conditions": "Unknown", "location": location}

        weather = self.data_store["weather"][location]
        return {"temperature": weather["temperature"], "conditions": weather["conditions"], "location": location}

    @mcp_tool(description="Store a note with a given title", output_model=None)
    async def save_note(self, title: str, content: str) -> None:
        """Save a note with the given title and content.

        Args:
            title: The title of the note
            content: The content of the note
        """
        logger.info(f"Saving note: {title}")
        self.data_store["notes"][title] = content
        return None

    @mcp_tool(description="Get a list of all saved notes")
    async def list_notes(self) -> Dict[str, List[str]]:
        """Get a list of all saved notes.

        Returns:
            List of note titles
        """
        return {"notes": list(self.data_store["notes"].keys())}

    @mcp_tool(description="Get the content of a note by title")
    async def get_note(self, title: str) -> Dict[str, Optional[str]]:
        """Get the content of a note by its title.

        Args:
            title: The title of the note to retrieve

        Returns:
            The note content or None if not found
        """
        content = self.data_store["notes"].get(title)
        return {"content": content}

    @mcp_prompt(description="Generate a creative story about the given topic")
    async def generate_story(self, topic: str, length: int = 100) -> str:
        """Generate a creative story about the given topic.

        Args:
            topic: The topic to create a story about
            length: The approximate length of the story in words

        Returns:
            A creative story
        """
        return (
            f"This prompt would be handled by the LLM. "
            f"It would generate a story about {topic} with approximately {length} words."
        )

    @mcp_resource(uri="/logo.png", mime_type="image/png", description="Get the logo image")
    async def get_logo(self) -> bytes:
        """Get the logo image.

        Returns:
            The logo image as bytes
        """
        # In a real application, this would return an actual image
        return b"This would be binary image data"

    async def setup(self) -> None:
        """Set up the agent."""
        logger.info(f"Setting up {self.name}")
        # Add any additional setup logic here


async def main():
    """Run the example MCP agent."""
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Create the agent
    agent = MyMcpAgent("mcp_example_agent")

    # Create an SSE communicator in server mode
    port = int(os.environ.get("MCP_PORT", 8000))
    communicator = McpSseCommunicator(server_mode=True, port=port)

    # Set the communicator for the agent
    agent.set_communicator(communicator)

    # Start the agent
    await agent.start()

    logger.info(f"MCP agent server running on port {port}")
    logger.info("Press Ctrl+C to stop")

    try:
        # Keep the agent running
        await agent.run()
    except KeyboardInterrupt:
        logger.info("Stopping agent")
    finally:
        # Stop the agent
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
