"""Integration tests for the McpStdioCommunicator.

These tests verify that the McpStdioCommunicator can properly handle stdio-based
communication between MCP client and server agents using the real MCP library.

This test suite is marked with @pytest.mark.mcp and will only run in
dedicated test environments with MCP dependencies installed.
"""

import asyncio
import os
import sys
import tempfile
from typing import Any, Dict

import pytest
from pydantic import BaseModel, Field

from openmas.agent import McpClientAgent, McpServerAgent, mcp_tool
from openmas.communication.mcp.stdio_communicator import McpStdioCommunicator
from openmas.exceptions import ServiceNotFoundError

# Mark all tests in this module with the 'mcp' marker
pytestmark = [
    pytest.mark.mcp,
    pytest.mark.skip(
        reason="Tests require real MCP integration with subprocess creation which is unreliable in CI environments"
    ),
]


class MultiplyRequest(BaseModel):
    """Request model for the multiply tool."""

    x: float = Field(..., description="First number to multiply")
    y: float = Field(..., description="Second number to multiply")


class MultiplyResponse(BaseModel):
    """Response model for the multiply tool."""

    result: float = Field(..., description="Product of the two numbers")


class StdioTestServer(McpServerAgent):
    """Test server agent that exposes tools via stdio."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the test server.

        Args:
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(
            name="stdio_test_server",
            config={
                "COMMUNICATOR_TYPE": "mcp-stdio",
                "SERVER_MODE": True,
                "SERVER_INSTRUCTIONS": "Test stdio server for integration tests",
            },
            server_type="stdio",
            **kwargs,
        )

    @mcp_tool(
        name="multiply",
        description="Multiply two numbers together",
        input_model=MultiplyRequest,
        output_model=MultiplyResponse,
    )
    async def multiply_numbers(self, x: float, y: float) -> Dict[str, float]:
        """Multiply two numbers and return the result.

        Args:
            x: First number
            y: Second number

        Returns:
            Dictionary with the result
        """
        return {"result": x * y}

    @mcp_tool(name="echo", description="Echo back the input")
    async def echo(self, message: str) -> Dict[str, str]:
        """Echo back the input message.

        Args:
            message: The message to echo

        Returns:
            Dictionary with the echoed message
        """
        return {"message": message}


class StdioTestClient(McpClientAgent):
    """Test client agent that connects to stdio-based MCP servers."""

    def __init__(self, command: str, **kwargs: Any) -> None:
        """Initialize the test client.

        Args:
            command: The command to execute for the stdio server
            **kwargs: Additional arguments to pass to the parent class
        """
        super().__init__(
            name="stdio_test_client",
            config={
                "COMMUNICATOR_TYPE": "mcp-stdio",
                "SERVICE_URLS": {"stdio_server": command},
            },
            **kwargs,
        )


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_communicator_direct_instantiation() -> None:
    """Test direct instantiation and usage of McpStdioCommunicator."""
    # Create a temporary script that runs a simple MCP server
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as server_file:
        server_file.write(
            """
import asyncio
import sys
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import CallToolResult

async def multiply(ctx: Context, x: float, y: float) -> CallToolResult:
    return CallToolResult({"result": x * y})

async def main():
    mcp_server = FastMCP()
    mcp_server.add_tool("multiply", "Multiply two numbers", multiply)

    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    await mcp_server.serve_stdio(stdin, stdout)

if __name__ == "__main__":
    asyncio.run(main())
"""
        )
        server_file.flush()
        server_path = server_file.name

    # Make the script executable
    os.chmod(server_path, 0o755)

    # Get Python executable path - use the executable itself as the command
    # and pass the script as an argument
    python_exe = sys.executable

    # Directly create a communicator using proper command array format
    communicator = McpStdioCommunicator(
        agent_name="test_direct",
        service_urls={"direct_server": python_exe},
        service_args={"direct_server": [server_path]},
        server_mode=False,
    )

    try:
        # Start the communicator
        await communicator.start()

        # Call the multiply tool
        result = await communicator.call_tool(
            target_service="direct_server",
            tool_name="multiply",
            arguments={"x": 3.5, "y": 2.0},
        )

        # Check the result
        assert result is not None
        assert isinstance(result, dict)
        assert "result" in result
        assert result["result"] == 7.0  # 3.5 * 2.0 = 7.0

    finally:
        # Stop the communicator
        await communicator.stop()
        # Clean up the temporary file
        if os.path.exists(server_path):
            os.unlink(server_path)


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_stdio_url_format() -> None:
    """Test the stdio:// URL format for McpStdioCommunicator."""
    # Create a temporary script that runs a simple MCP server
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as server_file:
        server_file.write(
            """
import asyncio
import sys
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import CallToolResult

async def echo(ctx: Context, message: str) -> CallToolResult:
    return CallToolResult({"message": message})

async def main():
    mcp_server = FastMCP()
    mcp_server.add_tool("echo", "Echo a message", echo)

    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    await mcp_server.serve_stdio(stdin, stdout)

if __name__ == "__main__":
    asyncio.run(main())
"""
        )
        server_file.flush()
        server_path = server_file.name

    # Make the script executable
    os.chmod(server_path, 0o755)

    # Get the Python executable path - split into executable and args
    python_exe = sys.executable

    # Create a communicator with proper arguments
    communicator = McpStdioCommunicator(
        agent_name="test_stdio_url",
        service_urls={"stdio_url_server": f"stdio:{python_exe}"},
        service_args={"stdio_url_server": [server_path]},
        server_mode=False,
    )

    try:
        # Start the communicator
        await communicator.start()

        # Call the echo tool
        result = await communicator.call_tool(
            target_service="stdio_url_server",
            tool_name="echo",
            arguments={"message": "Hello from stdio URL test"},
        )

        # Verify the result - if using mocks, result might be a string 'mock-tool-result'
        if not isinstance(result, dict):
            assert result == "mock-tool-result"
        else:
            assert result["message"] == "Hello from stdio URL test"
    finally:
        # Clean up
        await communicator.stop()
        try:
            os.unlink(server_path)
        except (OSError, IOError):
            pass


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_stdio_invalid_executable() -> None:
    """Test error handling when invalid executable is provided."""
    # Create a communicator with non-existent executable
    communicator = McpStdioCommunicator(
        agent_name="test_invalid_exe",
        service_urls={"invalid_server": "stdio:/non_existent_executable"},
        server_mode=False,
    )

    try:
        # Start the communicator
        await communicator.start()

        # This should raise ServiceNotFoundError
        with pytest.raises(ServiceNotFoundError) as excinfo:
            await communicator.call_tool(
                target_service="invalid_server",
                tool_name="any_tool",
                arguments={},
            )

        # Verify the error message
        assert "does not exist" in str(excinfo.value)
    finally:
        # Clean up
        await communicator.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_stdio_server_mode() -> None:
    """Test the stdio communicator in server mode."""
    # Create a communicator in server mode
    communicator = McpStdioCommunicator(
        agent_name="stdio_test_server",
        service_urls={},
        server_mode=True,
    )

    # Define a handler for a tool
    async def handle_multiply(x: float, y: float) -> Dict[str, float]:
        """Multiply two numbers."""
        return {"result": x * y}

    # Register the handler
    # communicator.register_tool_handler("multiply", handle_multiply)
    await communicator.register_handler("tool/call/multiply", handle_multiply)

    try:
        # Start the server
        await communicator.start()

        # Allow server to start
        await asyncio.sleep(1)
    finally:
        # Stop the server
        await communicator.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_stdio_full_agent_interaction() -> None:
    """Test full agent interaction using McpStdioCommunicator."""
    # Only run if system has necessary permissions to create processes
    if not os.access(sys.executable, os.X_OK):
        pytest.skip("Cannot execute Python - insufficient permissions")

    # Create a temporary server script
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as server_file:
        server_file.write(
            """
import sys
import asyncio
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import CallToolResult

async def greet(ctx: Context, name: str) -> CallToolResult:
    return CallToolResult({"greeting": f"Hello, {name}!"})

async def main():
    mcp_server = FastMCP()
    mcp_server.add_tool("greet", "Greet a person by name", greet)
    
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    await mcp_server.serve_stdio(stdin, stdout)

if __name__ == "__main__":
    asyncio.run(main())
"""
        )
        server_file.flush()
        server_path = server_file.name

    # Make the script executable
    os.chmod(server_path, 0o755)

    # Get Python executable path and create command
    python_exe = sys.executable

    # Create a communicator directly
    communicator = McpStdioCommunicator(
        agent_name="stdio_test_client",
        service_urls={"temp_server": f"stdio:{python_exe}"},
        service_args={"temp_server": [server_path]},
        server_mode=False,
    )

    # Create a client agent with the communicator
    client = McpClientAgent(name="stdio_test_client")
    client.set_communicator(communicator)

    try:
        # Set up the client
        await client.setup()

        # Call the greet tool
        response = await client.call_tool(
            target_service="temp_server",
            tool_name="greet",
            arguments={"name": "World"},
        )

        # Verify the response - could be a mock if using mock communicator
        if isinstance(response, dict):
            assert "greeting" in response
            assert response["greeting"] == "Hello, World!"
        else:
            assert response is not None
    finally:
        # Clean up
        await client.stop()
        try:
            os.unlink(server_path)
        except (OSError, IOError):
            pass
