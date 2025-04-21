"""Example of how to create an MCP server with SimpleMAS."""

import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

from mcp.messages import Message, MessageRole, TextContent

from simple_mas.agent import Agent
from simple_mas.communication.mcp import McpServerWrapper
from simple_mas.config import AgentConfig
from simple_mas.logging import get_logger, setup_logging

# Set up logging
setup_logging()
logger = get_logger(__name__)


class McpServer:
    """Example MCP server using the MCP SDK."""

    def __init__(self, name: str, instructions: Optional[str] = None):
        """Initialize the MCP server.

        Args:
            name: The name of the server
            instructions: Optional instructions for the server
        """
        self.mcp = McpServerWrapper(name=name, instructions=instructions)
        self._setup_tools()
        self._setup_prompts()
        self._setup_resources()

    def _setup_tools(self) -> None:
        """Set up tools for the MCP server."""

        @self.mcp.tool(description="Generate text based on a prompt")
        async def generate_text(prompt: str) -> str:
            """Generate text based on a prompt.

            Args:
                prompt: The prompt to generate text for

            Returns:
                The generated text
            """
            logger.info(f"Generating text for prompt: {prompt}")
            return f"Generated text in response to: {prompt}"

        @self.mcp.tool(description="Analyze the sentiment of text")
        async def analyze_sentiment(text: str) -> Dict[str, Any]:
            """Analyze the sentiment of text.

            Args:
                text: The text to analyze

            Returns:
                A dictionary with sentiment analysis results
            """
            logger.info(f"Analyzing sentiment for text: {text}")
            sentiment = "positive" if "good" in text.lower() else "negative"
            return {"sentiment": sentiment, "confidence": 0.85}

    def _setup_prompts(self) -> None:
        """Set up prompts for the MCP server."""

        @self.mcp.prompt(description="A simple question-answering prompt")
        async def simple_question(question: str) -> List[Message]:
            """Create a simple question-answering prompt.

            Args:
                question: The question to answer

            Returns:
                A list of messages forming the prompt
            """
            logger.info(f"Creating prompt for question: {question}")
            return [
                Message(role=MessageRole.SYSTEM, content=[TextContent(text="You are a helpful assistant.")]),
                Message(role=MessageRole.USER, content=[TextContent(text=question)]),
            ]

    def _setup_resources(self) -> None:
        """Set up resources for the MCP server."""

        @self.mcp.resource(
            "resource://example", name="Example Resource", description="An example resource", mime_type="text/plain"
        )
        async def example_resource() -> str:
            """Provide the content for the example resource.

            Returns:
                The resource content as a string
            """
            logger.info("Reading example resource")
            return "This is an example resource."

        @self.mcp.resource(
            "resource://{id}",
            name="Parameterized Resource",
            description="A resource with parameters",
            mime_type="text/plain",
        )
        async def parameterized_resource(id: str) -> str:
            """Provide content for a parameterized resource.

            Args:
                id: The resource ID

            Returns:
                The resource content as a string
            """
            logger.info(f"Reading parameterized resource with ID: {id}")
            return f"This is resource with ID: {id}"

    def run(self, transport: str = "stdio") -> None:
        """Run the MCP server.

        Args:
            transport: Transport protocol to use ("stdio" or "sse")
        """
        logger.info(f"Starting MCP server with transport: {transport}")
        self.mcp.run(transport)

    async def run_async(self, transport: str = "stdio") -> None:
        """Run the MCP server asynchronously.

        Args:
            transport: Transport protocol to use ("stdio" or "sse")
        """
        logger.info(f"Starting MCP server with transport: {transport}")
        if transport == "sse":
            await self.mcp.run_sse_async()
        else:
            await self.mcp.run_stdio_async()


class ServerAgent(Agent):
    """Agent that hosts an MCP server."""

    def __init__(self, config: AgentConfig, server: McpServer):
        """Initialize the server agent.

        Args:
            config: Agent configuration
            server: MCP server to host
        """
        super().__init__(config)
        self.server = server

    async def run(self) -> None:
        """Run the agent, which hosts the MCP server."""
        logger.info("Starting MCP server agent")

        # The transport type can be configured via environment variable
        transport = os.environ.get("MCP_TRANSPORT", "stdio")

        # Run the server asynchronously
        await self.server.run_async(transport)


def main_cli() -> None:
    """Run the MCP server as a standalone CLI application."""
    # Set up the MCP server
    server = McpServer(name="SimpleMasServer", instructions="This is an example MCP server hosted by SimpleMAS.")

    # Get the transport type from command line arguments or environment
    transport = "stdio"
    if len(sys.argv) > 1:
        transport = sys.argv[1]
    elif os.environ.get("MCP_TRANSPORT"):
        transport = os.environ.get("MCP_TRANSPORT")

    # Run the server
    server.run(transport)


async def main_agent() -> None:
    """Run the MCP server as a SimpleMAS agent."""
    # Set up the MCP server
    server = McpServer(name="SimpleMasServer", instructions="This is an example MCP server hosted by SimpleMAS.")

    # Create and run the agent
    config = AgentConfig(name="McpServerAgent")
    agent = ServerAgent(config=config, server=server)

    # Start and run the agent
    await agent.start()
    await agent.run()
    # The agent.run() method will block indefinitely as it hosts the server


if __name__ == "__main__":
    # Check if we should run as an agent or as a CLI
    if os.environ.get("RUN_AS_AGENT", "false").lower() == "true":
        asyncio.run(main_agent())
    else:
        main_cli()
