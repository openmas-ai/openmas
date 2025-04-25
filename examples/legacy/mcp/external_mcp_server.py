#!/usr/bin/env python3
"""
Example demonstrating how to connect to an external MCP server.

This example shows how to create agents that connect to an external MCP server.
To run this example, you need to have a running MCP server. You can either:
1. Run a local MCP server using `poetry run python -m mcp.server.fastmcp`
2. Connect to a remote server by setting the MCP_SERVER_URL environment variable
"""

import asyncio
import logging
import os

from mcp.client.sse import sse_client
from mcp.types import TextContent

from openmas.agent.base import BaseAgent
from openmas.communication.mcp import MCPCommunicator
from openmas.config import AgentConfig

# Default MCP server URL for local testing
DEFAULT_MCP_URL = "http://localhost:8000"


class MCPClientAgent(BaseAgent):
    """Agent that connects to an external MCP server."""

    async def setup(self) -> None:
        """Set up the agent by configuring the MCP client."""
        self.logger.info(f"Setting up MCP client agent: {self.name}")

        # Get the MCP server URL from config or environment
        self.mcp_server_url = self.config.get("mcp_server_url", os.getenv("MCP_SERVER_URL", DEFAULT_MCP_URL))
        self.logger.info(f"Using MCP server URL: {self.mcp_server_url}")

        # Initialize MCP communicator
        if not hasattr(self, "communicator") or self.communicator is None:
            self.communicator = MCPCommunicator(agent_name=self.name)

        # Register message handlers
        self.register_message_handler("text", self.handle_text_message)

        self.logger.info(f"Agent {self.name} setup complete")

    async def run(self) -> None:
        """Run the agent by connecting to the MCP server and processing messages."""
        self.logger.info(f"Starting MCP client agent: {self.name}")

        # Create session with MCP server
        async with sse_client(f"{self.mcp_server_url}/sessions/agent/{self.name}") as session:
            self.session = session

            # Send initial greeting
            await self.send_message(f"Hello from {self.name}! I'm ready to collaborate.")

            # Process incoming messages
            async for event in session:
                if event.event == "message":
                    content = event.data
                    self.logger.debug(f"Received message: {content}")

                    # Handle different message types
                    if isinstance(content, TextContent):
                        await self.handle_text_message(content.text)
                    else:
                        self.logger.warning(f"Unsupported message type: {type(content)}")

    async def handle_text_message(self, text: str) -> None:
        """Handle incoming text messages."""
        self.logger.info(f"Received text message: {text}")

        # Example: Echo the message back with the agent's name
        response = f"{self.name} received: {text}"
        await self.send_message(response)

    async def send_message(self, text: str) -> None:
        """Send a text message through the MCP server."""
        if hasattr(self, "session") and self.session:
            self.logger.debug(f"Sending message: {text}")
            await self.session.send_message(TextContent(text=text, type="text"))
        else:
            self.logger.error("Cannot send message: no active session")

    async def shutdown(self) -> None:
        """Clean up resources when the agent is shutting down."""
        self.logger.info(f"Shutting down MCP client agent: {self.name}")
        # Close session if it exists
        if hasattr(self, "session") and self.session:
            await self.session.close()
        self.logger.info(f"Agent {self.name} shutdown complete")


async def main() -> None:
    """Main function to start the agents."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    # Get MCP server URL from environment or use default
    mcp_server_url = os.getenv("MCP_SERVER_URL", DEFAULT_MCP_URL)

    # Create agent configurations
    agent1_config = AgentConfig(
        name="agent1",
        config={
            "mcp_server_url": mcp_server_url,
        },
    )

    agent2_config = AgentConfig(
        name="agent2",
        config={
            "mcp_server_url": mcp_server_url,
        },
    )

    # Create and start agents
    agent1 = MCPClientAgent(config=agent1_config)
    agent2 = MCPClientAgent(config=agent2_config)

    try:
        # Start agents and store tasks
        await agent1.start()
        await agent2.start()

        # Keep the program running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        # Handle graceful shutdown
        print("Shutting down agents...")
        await agent1.stop()
        await agent2.stop()
    finally:
        print("Example completed")


if __name__ == "__main__":
    asyncio.run(main())
