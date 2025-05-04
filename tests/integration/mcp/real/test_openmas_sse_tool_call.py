"""Integration test for OpenMAS MCP SSE tool call using real MCP communication.

This test validates that the OpenMAS MCP SSE integration works correctly
with real MCP communication (not mocked).

The test follows the patterns established in the example_02_mcp/01_mcp_sse_tool_call
example project, which has been verified to work correctly.

NOTE: This test is skipped by default because it requires a proper MCP setup
with real network connectivity between the server and client. To run it manually:

    poetry run pytest tests/integration/mcp/real/test_openmas_sse_tool_call.py -v --run-real-mcp
"""

import asyncio
import logging
import sys  # For checking command line arguments

# import random # No longer needed directly
from typing import Any, Dict, Optional

import pytest

from openmas.agent import BaseAgent
from openmas.config import AgentConfig
from openmas.exceptions import CommunicationError

# Correctly placed import
from .utils import McpTestHarness, TransportType  # Only import necessary items

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


# Skip by default unless --run-real-mcp is specified
skip_real_mcp = True

# Try to determine if --run-real-mcp was specified
try:
    if "--run-real-mcp" in sys.argv:
        skip_real_mcp = False
except Exception:  # Specify exception type
    pass


# Try importing McpSseCommunicator directly for isolated testing
try:
    from openmas.communication.mcp.sse_communicator import McpSseCommunicator

    HAS_COMMUNICATOR = True
except ImportError:
    McpSseCommunicator = None  # type: ignore
    HAS_COMMUNICATOR = False


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
            if hasattr(self.communicator, "register_tool"):
                await self.communicator.register_tool(
                    name=tool_name,
                    description="Process text input by converting to uppercase and counting words",
                    function=self.process_text_handler,
                )
                logger.info(f"Registered MCP tool: {tool_name}")
            else:
                # For non-MCP communicators, register a standard handler
                await self.communicator.register_handler(f"tool/call/{tool_name}", self.process_text_handler)
                logger.info(f"Registered handler for tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error registering tool/handler: {e}")
            raise

        logger.info(f"{self.name} setup complete")

    async def process_text_handler(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process text by converting to uppercase and counting words.

        Args:
            payload: Dictionary containing the text to process

        Returns:
            Dictionary containing the processed result
        """
        logger.info(f"Process text handler received payload: {payload}")

        # Check if the text field is present
        if "text" not in payload:
            result = {"error": "No text field in payload", "status": "error"}
            logger.warning(f"Missing text field in payload: {payload}")
            return result

        # Process the text
        text = payload["text"]
        if not text:
            result = {"error": "Empty text input", "status": "error"}
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
        payload = {"text": text}

        try:
            # Call the tool with timeout
            if hasattr(self.communicator, "call_tool"):
                result = await asyncio.wait_for(
                    self.communicator.call_tool(
                        target_service="tool_provider",
                        tool_name=tool_name,
                        arguments=payload,
                    ),
                    timeout=timeout,
                )
            else:
                result = await asyncio.wait_for(
                    self.communicator.send_request(
                        target_service="tool_provider",
                        method=f"tool/call/{tool_name}",
                        params=payload,
                    ),
                    timeout=timeout,
                )

            # Ensure result is Dict[str, Any] to satisfy mypy
            if not isinstance(result, dict):
                result_dict: Dict[str, Any] = {"raw_result": str(result)}
                logger.warning(f"Expected dict result, got {type(result)}")
                self.result = result_dict
                return result_dict

            # Store and return the result as a properly typed Dict[str, Any]
            typed_result: Dict[str, Any] = result
            self.result = typed_result
            logger.info(f"Received tool result: {typed_result}")
            return typed_result

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
@pytest.mark.skipif(skip_real_mcp, reason="Skipped by default. Use --run-real-mcp to enable.")
async def test_openmas_mcp_sse_integration() -> None:
    """Test OpenMAS MCP SSE integration using the McpTestHarness.

    This test:
    1. Starts the `mcp_sse_test_server.py` script using McpTestHarness.
    2. Verifies the server starts and is reachable via HTTP.
    3. Creates a client agent (ToolUserAgent) configured to connect to the server's SSE endpoint.
    4. Makes a tool call from the client agent to the server agent.
    5. Validates the response.
    6. Cleans up the server process via the harness.

    Note: This test requires a proper environment setup and is skipped by default.
    Run with --run-real-mcp to enable.
    """
    if not HAS_COMMUNICATOR:
        pytest.skip("McpSseCommunicator not available for import")

    # Define the server script path first
    server_script_path = "tests/integration/mcp/real/sse_server_script.py"  # Use the working server script
    harness = McpTestHarness(TransportType.SSE, script_path=server_script_path)  # Pass script path here
    logger.info(f"Using test port: {harness.test_port}")

    try:
        # Start the server script as a subprocess via the harness
        logger.info(f"Starting server script: {server_script_path}")
        # sse_server_script.py takes --port and optionally --host
        # Use 127.0.0.1 explicitly for host binding for consistency
        process = await harness.start_server(additional_args=["--host", "127.0.0.1", "--port", str(harness.test_port)])
        if process.returncode is not None:
            # stderr, stdout = await harness.read_process_output() # Method doesn't exist
            # logger.error(f"Server process failed to start. Code: {process.returncode}\nStderr: {stderr}\nStdout: {stdout}")
            pytest.fail(f"Server process failed to start immediately. Code: {process.returncode}")
            return  # Ensure mypy knows process is not None if fail occurs

        logger.info("Server process started, waiting for readiness signal & HTTP check...")
        # Harness waits for stderr signal (SSE_SERVER_URL=...) AND performs HTTP check on /sse
        startup_ok = await harness.verify_server_startup(timeout=25.0)  # Increased timeout
        assert startup_ok, "Server startup verification failed (check harness logs and server script stderr)"
        assert harness.server_url, "Server URL not successfully parsed from harness startup"  # Should include /sse
        logger.info(f"Server ready, Harness URL: {harness.server_url}")

        # --- Client Agent Setup and Connection ---
        logger.info("Configuring and starting ToolUserAgent...")
        user_config = AgentConfig(
            name="tool_user_agent",
            communicator_type="mcp-sse",
            communicator_options={
                "server_mode": False,  # Explicitly client mode
            },
            service_urls={"provider_service": harness.server_url},  # Use the URL obtained by harness
        )
        user = ToolUserAgent(config=user_config)
        try:
            await user.start()
            logger.info("ToolUserAgent started successfully.")

            # Call the registered test tool via the user agent's communicator
            # sse_server_script.py provides an 'echo' tool which expects a 'message' key
            tool_call_args = {"message": "hello from client via OpenMAS"}
            logger.info(f"Calling 'echo' tool with args: {tool_call_args}")
            result = await user.communicator.call_tool(
                target_service="provider_service",  # Must match key in user_config.service_urls
                tool_name="echo",  # Tool name from sse_server_script.py
                arguments=tool_call_args,
            )

            logger.info(f"Tool call result received: {result}")

            # --- Assertions --- # Check the structure and content
            assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
            assert "echoed" in result, "'echoed' key missing from result"
            assert result.get("echoed") == tool_call_args["message"], "Echoed message mismatch"

            # Ensure the result is explicitly typed as Dict[str, Any] to fix mypy issue
            result_dict: Dict[str, Any] = result

            logger.info("Assertions passed!")

        finally:
            # Ensure agent is stopped even if assertions fail
            if "user" in locals() and user._is_running:
                logger.info("Stopping ToolUserAgent...")
                await user.stop()
                logger.info("ToolUserAgent stopped.")

    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        # stderr, stdout = await harness.read_process_output() # Ensure this remains commented out
        # logger.error(f"Server stderr:\n{stderr}")           # Ensure this remains commented out
        # logger.error(f"Server stdout:\n{stdout}")           # Ensure this remains commented out
        pytest.fail(f"Test failed with exception: {e}")
    finally:
        # --- Cleanup --- #
        logger.info("Cleaning up test harness (terminating server process)...")
        await harness.cleanup()
        logger.info("Test harness cleanup complete.")

    logger.info("test_openmas_mcp_sse_integration finished.")
