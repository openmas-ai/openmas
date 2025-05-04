"""Tool user agent that calls an MCP tool via stdio."""

from openmas.agent import BaseAgent
from openmas.logging import get_logger

logger = get_logger(__name__)


class ToolUserAgent(BaseAgent):
    """Agent that uses an MCP tool over stdio.

    This agent calls the "process_data" tool provided by the ToolProviderAgent,
    sends some text data, and processes the result.
    """

    async def setup(self) -> None:
        """Set up the agent."""
        logger.info("Setting up ToolUserAgent")
        self.result = None
        logger.info("ToolUserAgent setup complete")

    async def run(self) -> None:
        """Run the agent by calling the process_data tool."""
        logger.info("ToolUserAgent running, calling process_data tool")

        # Prepare the data to send to the tool
        tool_payload = {"text": "Hello, this is a sample text that needs processing."}
        tool_name = "process_data"

        try:
            # Try to use MCP call_tool if available, otherwise use send_request
            logger.info(f"Calling tool '{tool_name}' with payload: {tool_payload}")

            if hasattr(self.communicator, "call_tool"):
                # Call the process_data tool using MCP call_tool
                result = await self.communicator.call_tool(
                    target_service="tool_provider", tool_name=tool_name, arguments=tool_payload
                )
            else:
                # For testing with MockCommunicator, use send_request with the tool/call/ prefix
                result = await self.communicator.send_request(
                    target_service="tool_provider", method=f"tool/call/{tool_name}", params=tool_payload
                )

            # Store the result for verification in tests
            self.result = result

            # Log the result
            logger.info(f"Received tool result: {result}")

            if result.get("status") == "success":
                logger.info(f"Successfully processed text. Word count: {result.get('word_count')}")
                logger.info(f"Processed text: {result.get('processed_text')}")
            else:
                logger.error(f"Tool call failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error calling tool: {e}")

        logger.info("ToolUserAgent completed its run method")

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info("ToolUserAgent shutting down")
