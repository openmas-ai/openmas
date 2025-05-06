"""Integration test for OpenMAS MCP SSE tool call using real MCP communication.

This test validates that the OpenMAS MCP SSE integration works correctly
with real MCP communication (not mocked).

The test follows the patterns established in the example_02_mcp/01_mcp_sse_tool_call
example project, which has been verified to work correctly.

NOTE: This test uses the '--run-real-mcp' custom pytest flag to control execution.
It's skipped if the flag is not provided because it requires real network
communication and MCP dependencies.

To run using tox (recommended, includes the flag automatically):
    tox -e integration-real-mcp

To run manually with pytest:
    poetry run pytest tests/integration/mcp/real/test_openmas_sse_tool_call.py -v --run-real-mcp
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import pytest

from openmas.agent import BaseAgent

# Import our communicator directly
from openmas.communication.mcp.sse_communicator import McpSseCommunicator
from openmas.exceptions import CommunicationError

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Skip the test if MCP is not installed
try:
    import mcp  # noqa: F401 Remove unused import error

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

skip_reason = "MCP package not installed"


class ToolProviderAgent(BaseAgent):
    """Agent that provides an MCP tool via SSE.

    This agent registers a tool called "process_text" that handles
    text processing operations.
    """

    async def setup(self) -> None:
        """Set up the agent by registering the MCP tool."""
        logger.info(f"Setting up {self.name}")

        # Register the process_text MCP tool
        tool_name = "process_text"

        try:
            # Register the tool if the communicator supports it
            await self.communicator.register_tool(
                name=tool_name,
                description="Process text input by converting to uppercase and counting words",
                function=self.process_text_handler,
            )
            logger.info(f"Registered MCP tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error registering tool: {e}")
            raise

        logger.info(f"{self.name} setup complete")

    async def process_text_handler(self, text: str) -> Dict[str, Any]:
        """Process text by converting to uppercase and counting words.

        Args:
            text: The text to process

        Returns:
            Dictionary containing the processed result
        """
        logger.info(f"Process text handler received text: {text}")

        # Process the text
        if not text:
            raise ValueError("Empty text input")
        else:
            processed_text = text.upper()
            word_count = len(text.split())
            result = {"processed_text": processed_text, "word_count": str(word_count), "status": "success"}

        logger.info(f"Process text handler returning result: {result}")
        return result

    async def run(self) -> None:
        """Run the agent.

        The tool provider agent waits for incoming tool calls.
        """
        logger.info(f"{self.name} running, waiting for tool calls")

        # Keep the agent alive
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info(f"{self.name} run loop cancelled")
            raise

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info(f"{self.name} shutting down")


class ToolUserAgent(BaseAgent):
    """Agent that uses an MCP tool via SSE.

    This agent calls the "process_text" tool provided by the ToolProviderAgent.
    """

    async def setup(self) -> None:
        """Set up the agent."""
        logger.info(f"Setting up {self.name}")
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[Dict[str, str]] = None
        logger.info(f"{self.name} setup complete")

    async def call_process_text(self, text: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Call the process_text tool on the tool provider.

        Args:
            text: The text to process
            timeout: Timeout in seconds

        Returns:
            The tool result

        Raises:
            CommunicationError: If the tool call fails
            asyncio.TimeoutError: If the tool call times out
        """
        logger.info(f"Calling process_text tool with text: {text}")

        tool_name = "process_text"

        # Create a payload that explicitly sets the text field for MCP 1.7.1
        payload = {
            "text": text,
            # Optionally add a fallback content field in MCP 1.7.1 format
            # Some MCP servers expect this format instead
            "content": [{"type": "text", "text": text}],
        }

        logger.info(f"Sending payload to process_text tool: {payload}")

        try:
            # Call the tool with timeout
            result = await asyncio.wait_for(
                self.communicator.call_tool(
                    target_service="tool_provider",
                    tool_name=tool_name,
                    arguments=payload,
                ),
                timeout=timeout,
            )

            # Store and return the result
            self.result = result
            logger.info(f"Received tool result: {result}")
            return result

        except asyncio.TimeoutError:
            error_msg = f"Tool call timed out after {timeout} seconds"
            logger.error(error_msg)
            self.error = {"error": error_msg, "status": "timeout"}
            raise
        except Exception as e:
            error_msg = f"Error calling tool: {e}"
            logger.error(error_msg)
            self.error = {"error": str(e), "status": "error"}
            raise CommunicationError(f"Failed to call {tool_name}: {e}")

    async def run(self) -> None:
        """Run the agent."""
        logger.info(f"{self.name} running")

        # In a real agent, you might have application logic here
        # For this test, the agent just waits to be called explicitly
        await asyncio.sleep(0.1)

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info(f"{self.name} shutting down")


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_MCP, reason=skip_reason)
async def test_openmas_mcp_sse_integration() -> None:
    """Test OpenMAS MCP SSE integration with real agents.

    This test:
    1. Creates and starts a tool provider agent with the sse communicator in server mode
    2. Creates and starts a tool user agent with the sse communicator in client mode
    3. Has the tool user call the process_text tool on the provider
    4. Verifies that the tool call works correctly
    """
    # Use a different port than the example to avoid conflicts
    provider_port = 8081

    # Create communicator instances directly
    provider_service_urls: Dict[str, str] = {}  # Server doesn't need service URLs
    provider_communicator = McpSseCommunicator(
        agent_name="tool_provider",
        service_urls=provider_service_urls,
        server_mode=True,
        http_port=provider_port,
    )

    # Create the user communicator - it needs to know the provider's URL
    user_service_urls = {"tool_provider": f"http://localhost:{provider_port}"}
    user_communicator = McpSseCommunicator(
        agent_name="tool_user",
        service_urls=user_service_urls,
        server_mode=False,  # Client mode
    )

    # Create agents directly with local configs instead of AgentConfig objects
    # This avoids the config loading/validation mechanism that's causing the error
    provider_agent = ToolProviderAgent(
        name="tool_provider",
        config={"name": "tool_provider", "communicator_type": "mcp-sse"},
    )
    provider_agent.set_communicator(provider_communicator)

    user_agent = ToolUserAgent(
        name="tool_user",
        config={"name": "tool_user", "communicator_type": "mcp-sse"},
    )
    user_agent.set_communicator(user_communicator)

    # Start the provider agent first
    await provider_agent.start()

    try:
        # Start the user agent
        await user_agent.start()

        # Wait a bit for the server to be fully ready
        await asyncio.sleep(1.0)

        # Call the process_text tool
        test_text = "Hello, this is a test message for mcp sse tool call."
        result = await user_agent.call_process_text(test_text)

        # Verify the result
        assert result is not None, "Got None result from tool call"
        assert "status" in result, "Missing status field in result"
        assert result["status"] == "success", f"Expected status=success but got {result}"
        assert "processed_text" in result, "Missing processed_text field in result"
        assert result["processed_text"] == test_text.upper(), "Text was not properly processed"
        assert "word_count" in result, "Missing word_count field in result"
        assert str(result["word_count"]) == str(len(test_text.split())), "Word count is incorrect"

        # Test error handling - empty text
        try:
            await user_agent.call_process_text("")
            assert False, "Expected an exception for empty text input"
        except CommunicationError:
            # This is expected
            assert user_agent.error is not None, "Error state not captured"
            assert "status" in user_agent.error, "Missing status in error"
            assert user_agent.error["status"] == "error", "Wrong error status"

    finally:
        # Shutdown the agents
        await user_agent.stop()
        await provider_agent.stop()


@pytest.mark.asyncio
@pytest.mark.mcp
@pytest.mark.skipif(not HAS_MCP, reason=skip_reason)
async def test_mcp_sse_handler_modification() -> None:
    """Test that handler modifications in McpSseCommunicator work correctly."""

    # Define a simple test handler
    async def initial_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "initial", "payload": payload}

    # Define a replacement handler
    async def modified_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "modified", "payload": payload}

    # Create a server-mode communicator for testing
    test_port = 8090
    communicator = McpSseCommunicator(
        agent_name="test_server",
        service_urls={},
        server_mode=True,
        http_port=test_port,
    )

    # Register the initial handler
    method_name = "test/method"
    await communicator.register_handler(method_name, initial_handler)

    # Verify the handler was registered
    assert method_name in communicator.handlers
    assert communicator.handlers[method_name] == initial_handler

    # Replace the handler
    await communicator.register_handler(method_name, modified_handler)

    # Verify the handler was replaced
    assert communicator.handlers[method_name] == modified_handler

    # Clean up
    communicator.handlers.clear()
