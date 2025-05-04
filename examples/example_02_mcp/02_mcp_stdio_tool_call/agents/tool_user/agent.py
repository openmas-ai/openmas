"""Tool user agent that calls an MCP tool via stdio."""

import asyncio
from typing import Any, Dict, Optional

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
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[Dict[str, str]] = None
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

            # Set a timeout for the tool call to prevent hanging
            timeout_seconds = 10.0

            if hasattr(self.communicator, "call_tool"):
                # Call the process_data tool using MCP call_tool with timeout
                result = await self._call_tool_with_timeout(
                    target_service="tool_provider", tool_name=tool_name, arguments=tool_payload, timeout=timeout_seconds
                )
            else:
                # For testing with MockCommunicator, use send_request with the tool/call/ prefix
                result = await self._send_request_with_timeout(
                    target_service="tool_provider",
                    method=f"tool/call/{tool_name}",
                    params=tool_payload,
                    timeout=timeout_seconds,
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

        except asyncio.TimeoutError:
            error_msg = f"Tool call to '{tool_name}' timed out after {timeout_seconds} seconds"
            logger.error(error_msg)
            self.error = {"error": error_msg, "status": "timeout"}
        except Exception as e:
            error_msg = f"Error calling tool: {e}"
            logger.error(error_msg)
            self.error = {"error": str(e), "status": "error"}

        logger.info("ToolUserAgent completed its run method")

    async def _call_tool_with_timeout(
        self, target_service: str, tool_name: str, arguments: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        """Call a tool with a timeout to prevent hanging.

        Args:
            target_service: The name of the service providing the tool
            tool_name: The name of the tool to call
            arguments: The arguments to pass to the tool
            timeout: Timeout in seconds

        Returns:
            The result of the tool call

        Raises:
            asyncio.TimeoutError: If the call times out
        """
        return await asyncio.wait_for(
            self.communicator.call_tool(target_service=target_service, tool_name=tool_name, arguments=arguments),
            timeout=timeout,
        )

    async def _send_request_with_timeout(
        self, target_service: str, method: str, params: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        """Send a request with a timeout to prevent hanging.

        Args:
            target_service: The name of the target service
            method: The method to call
            params: The parameters to pass
            timeout: Timeout in seconds

        Returns:
            The response from the service

        Raises:
            asyncio.TimeoutError: If the request times out
        """
        return await asyncio.wait_for(
            self.communicator.send_request(target_service=target_service, method=method, params=params), timeout=timeout
        )

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info("ToolUserAgent shutting down")
