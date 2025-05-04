"""Tool provider agent that registers and exposes an MCP tool via SSE."""

import asyncio
from typing import Any, Dict

from openmas.agent import BaseAgent
from openmas.logging import get_logger

logger = get_logger(__name__)


class ToolProviderAgent(BaseAgent):
    """Agent that provides an MCP tool over SSE.

    This agent registers a tool called "process_data" that handles
    incoming data and returns a processed result.
    """

    async def setup(self) -> None:
        """Set up the agent by registering the MCP tool."""
        logger.info("Setting up ToolProviderAgent")

        # Register the process_data MCP tool
        tool_name = "process_data"

        try:
            # If using a real MCP communicator, register as a tool
            if hasattr(self.communicator, "register_tool"):
                await self.communicator.register_tool(
                    name=tool_name,
                    description="Process incoming data and return a result",
                    function=self.process_data_handler,
                )
                logger.info(f"Registered MCP tool: {tool_name}")
            # If using MockCommunicator or another non-MCP communicator,
            # register as a standard handler with the tool/call/ prefix
            else:
                await self.communicator.register_handler(f"tool/call/{tool_name}", self.process_data_handler)
                logger.info(f"Registered handler for tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error registering tool/handler: {e}")
            raise

        logger.info("ToolProviderAgent setup complete")

    async def process_data_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming tool calls by processing the provided data.

        Args:
            payload: Dictionary containing the data to process

        Returns:
            Dictionary containing the processed result
        """
        logger.info(f"Tool handler received data: {payload}")

        # Simple data processing - in a real-world scenario, this might involve
        # complex transformations, model inference, or other operations
        if "text" in payload:
            processed_text = payload["text"].upper()
            word_count = len(payload["text"].split())

            result = {"processed_text": processed_text, "word_count": word_count, "status": "success"}
        else:
            result = {"error": "No text field in payload", "status": "error"}

        logger.info(f"Tool handler returning result: {result}")
        return result

    async def run(self) -> None:
        """Run the agent.

        The tool provider agent doesn't need to actively do anything in its run method.
        It primarily waits for incoming tool calls and responds to them.
        """
        logger.info("ToolProviderAgent running, waiting for tool calls")

        # Keep the agent alive while waiting for tool calls
        while True:
            await asyncio.sleep(1)

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info("ToolProviderAgent shutting down")
