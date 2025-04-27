"""Integration tests for MCP communication components.

These tests verify that the McpStdioCommunicator and McpSseCommunicator components
can properly communicate between MCP client and server agents using the MCP library.

This test suite is marked with @pytest.mark.mcp and will only run in
dedicated test environments with MCP dependencies installed.
"""

import asyncio
import os
import tempfile
from typing import Any, Dict
from unittest import mock

import pytest
from pydantic import BaseModel, Field

from openmas.agent import McpAgent, McpClientAgent, McpServerAgent, mcp_prompt, mcp_resource, mcp_tool
from openmas.communication.mcp import McpSseCommunicator, McpStdioCommunicator
from openmas.exceptions import CommunicationError, ServiceNotFoundError

# Mark all tests in this module with the 'mcp' marker
pytestmark = pytest.mark.mcp


class AddRequest(BaseModel):
    """Request model for the add tool."""

    a: int = Field(..., description="First number to add")
    b: int = Field(..., description="Second number to add")


class AddResponse(BaseModel):
    """Response model for the add tool."""

    result: int = Field(..., description="Sum of the two numbers")


class PromptParameters(BaseModel):
    """Parameters for sample prompt."""

    topic: str = Field(..., description="Topic to write about")
    style: str = Field(..., description="Writing style")


class MCP_TestServer(McpServerAgent):
    """Test server agent that exposes tools, prompts, and resources."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the test server.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        # Call parent constructor
        super().__init__(
            name="test_server",
            config={
                "COMMUNICATOR_TYPE": "mock",
                "SERVER_MODE": True,
                "SERVER_INSTRUCTIONS": "Test server for integration tests",
            },
            **kwargs,
        )

        # Create a temporary file for the resource test
        self._temp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        self._temp_file.write("This is a test resource")
        self._temp_file.close()

    @mcp_tool(
        name="add",
        description="Add two numbers together",
        input_model=AddRequest,
        output_model=AddResponse,
    )
    async def add_numbers(self, a: int, b: int) -> Dict[str, int]:
        """Add two numbers and return the result.

        Args:
            a: First number
            b: Second number

        Returns:
            Dictionary with the result
        """
        return {"result": a + b}

    @mcp_tool(name="error_tool", description="A tool that always raises an error")
    async def error_tool(self) -> None:
        """Raise an error to test error handling.

        Raises:
            ValueError: Always raised
        """
        raise ValueError("This tool always fails")

    @mcp_prompt(
        name="sample_prompt",
        description="A sample prompt for testing",
    )
    async def sample_prompt(self, topic: str, style: str) -> str:
        """Generate a sample prompt.

        Args:
            topic: Topic to write about
            style: Writing style

        Returns:
            Formatted prompt text
        """
        return f"Write about {topic} in a {style} style."

    @mcp_resource(
        uri="/test-resource",
        name="test_resource",
        description="A test resource",
        mime_type="text/plain",
    )
    async def test_resource(self) -> bytes:
        """Return the content of the test resource.

        Returns:
            Resource content as bytes
        """
        with open(self._temp_file.name, "rb") as f:
            return f.read()

    async def cleanup(self) -> None:
        """Clean up temporary resources."""
        try:
            os.unlink(self._temp_file.name)
        except (OSError, IOError):
            pass


class MCP_TestClient(McpClientAgent):
    """Test client agent that connects to MCP servers."""

    def __init__(self, client_type: str = "stdio", **kwargs: Any) -> None:
        """Initialize the test client.

        Args:
            client_type: The type of client to create ('sse' or 'stdio')
            **kwargs: Additional arguments to pass to the parent class
        """
        # Setup a port that doesn't conflict with other tests
        port = 8765

        # Create appropriate communicator configuration
        if client_type == "stdio":
            communicator_type = "mcp-stdio"
            service_urls = {}  # We'll connect directly to the server
        elif client_type == "sse":
            communicator_type = "mcp-sse"
            service_urls = {"test_server": f"http://localhost:{port}/mcp"}
        else:
            raise ValueError(f"Unsupported client type: {client_type}")

        # Call parent constructor
        super().__init__(
            name="test_client",
            config={
                "COMMUNICATOR_TYPE": communicator_type,
                "SERVICE_URLS": service_urls,
            },
            **kwargs,
        )


@pytest.mark.asyncio
async def test_mcp_stdio_communicator_registration() -> None:
    """Test that McpStdioCommunicator can register tools, prompts, and resources."""
    # Create a mock communicator to test registration
    communicator = mock.AsyncMock(spec=McpStdioCommunicator)

    # Create a server with the mock communicator
    server = MCP_TestServer()
    server.set_communicator(communicator)

    # Setup the server
    await server.setup()

    # Verify that the tools, prompts, and resources were registered
    assert communicator.register_tool.call_count >= 2  # add and error_tool
    assert communicator.register_prompt.call_count >= 1  # sample_prompt
    assert communicator.register_resource.call_count >= 1  # test_resource

    # Cleanup
    await server.cleanup()


@pytest.mark.asyncio
async def test_mcp_sse_communicator_registration() -> None:
    """Test that McpSseCommunicator can register tools, prompts, and resources."""
    # Create a mock communicator to test registration
    communicator = mock.AsyncMock(spec=McpSseCommunicator)

    # Create a server with the mock communicator
    server = MCP_TestServer()
    server.set_communicator(communicator)

    # Setup the server
    await server.setup()

    # Verify that the tools, prompts, and resources were registered
    assert communicator.register_tool.call_count >= 2  # add and error_tool
    assert communicator.register_prompt.call_count >= 1  # sample_prompt
    assert communicator.register_resource.call_count >= 1  # test_resource

    # Cleanup
    await server.cleanup()


@pytest.mark.asyncio
async def test_connection_error_handling() -> None:
    """Test handling of connection errors in MCP communication."""
    # Create a mock communicator directly
    communicator = McpSseCommunicator(
        agent_name="test_client",
        service_urls={"test_server": "http://localhost:9999/mcp"},  # Non-existent server
        server_mode=False,
    )

    # Test that the error is properly propagated when trying to connect
    with pytest.raises((CommunicationError, ServiceNotFoundError)) as excinfo:
        # This should fail because the server doesn't exist
        await communicator.send_request(target_service="test_server", method="tool/call/add", params={"a": 1, "b": 2})

    # Check that the error contains an informative message
    assert "test_server" in str(excinfo.value)


@pytest.mark.asyncio
async def test_mcp_sampling_prompt() -> None:
    """Test sampling a prompt from an MCP server using mocks."""
    # Skip if the communicator doesn't support sampling
    if not hasattr(McpSseCommunicator, "sample_prompt"):
        pytest.skip("Communicator doesn't support sampling_prompt")

    # Create a mock response for the sample method
    mock_response = {
        "content": "This is a response about climate change that discusses global warming impacts.",
        "model": "claude-3-opus-20240229",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 25, "output_tokens": 12},
    }

    # Create a mock communicator with a custom sample_prompt implementation
    communicator = mock.AsyncMock(spec=McpSseCommunicator)
    communicator.sample_prompt.return_value = mock_response
    communicator._connect_to_service = mock.AsyncMock()

    # Create the client with our mock communicator
    client = McpAgent(name="test_client")
    client.set_communicator(communicator)

    # Call the sample_prompt method
    result = await client.sample_prompt(
        target_service="test_server",
        messages=[{"role": "user", "content": "Write about climate change in an informative style."}],
        system_prompt="You are a helpful assistant.",
        temperature=0.7,
        max_tokens=100,
    )

    # Verify the result
    assert result == mock_response
    assert "content" in result
    assert "climate change" in result["content"]

    # Verify the mock was called with the right arguments
    communicator.sample_prompt.assert_called_once()
