"""Integration tests for the interaction between McpAgent and McpSseCommunicator.

These tests verify that the McpAgent correctly interacts with McpSseCommunicator
in both server and client modes.

This test suite is marked with @pytest.mark.mcp and will only run in
dedicated test environments with MCP dependencies installed.
"""

import asyncio
from typing import Any, Dict

import pytest

from openmas.agent import McpAgent, mcp_tool
from openmas.communication.mcp import McpSseCommunicator

# Mark all tests in this module with the 'mcp' marker and skip them in CI environments
pytestmark = [
    pytest.mark.mcp,
    pytest.mark.skip(reason="Tests require real MCP server/client connections which are unreliable in CI environments"),
]


class SampleServerAgent(McpAgent):
    """Sample server agent with tools for testing."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the sample server agent."""
        # Set a unique port to avoid conflicts with other tests
        port = 8790

        # Create communicator first
        communicator = McpSseCommunicator(
            agent_name="sample_server",
            service_urls={},  # Not used in server mode
            server_mode=True,
            http_port=port,
            server_instructions="Sample server for agent-communicator interaction tests",
        )

        # Initialize the agent
        super().__init__(
            name="sample_server",
            config={
                "COMMUNICATOR_TYPE": "mcp-sse",
                "SERVER_MODE": True,
                "HTTP_PORT": port,
            },
            **kwargs,
        )

        # Set the communicator explicitly
        self.set_communicator(communicator)

    @mcp_tool(name="add", description="Add two numbers")
    async def add_numbers(self, a: int, b: int) -> Dict[str, Any]:
        """Add two numbers and return the result.

        Args:
            a: First number
            b: Second number

        Returns:
            Dictionary with sum
        """
        return {"sum": a + b, "operation": f"Added {a} and {b}"}

    @mcp_tool(name="multiply", description="Multiply two numbers")
    async def multiply_numbers(self, a: int, b: int) -> Dict[str, Any]:
        """Multiply two numbers and return the result.

        Args:
            a: First number
            b: Second number

        Returns:
            Dictionary with product
        """
        return {"product": a * b, "operation": f"Multiplied {a} and {b}"}


class SampleClientAgent(McpAgent):
    """Sample client agent for testing."""

    def __init__(self, server_port: int = 8790, **kwargs: Any) -> None:
        """Initialize the sample client agent.

        Args:
            server_port: Port of the server to connect to
            **kwargs: Additional arguments for the parent class
        """
        # The server name should match the name used in SampleServerAgent
        server_name = "sample_server"

        # Create the communicator first
        communicator = McpSseCommunicator(
            agent_name="sample_client",
            service_urls={server_name: f"http://localhost:{server_port}/mcp"},
            server_mode=False,
        )

        # Initialize the agent
        super().__init__(
            name="sample_client",
            config={
                "COMMUNICATOR_TYPE": "mcp-sse",
                "SERVICE_URLS": {server_name: f"http://localhost:{server_port}/mcp"},
            },
            **kwargs,
        )

        # Set the communicator explicitly
        self.set_communicator(communicator)


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_agent_communicator_interaction() -> None:
    """Test the interaction between McpAgent and McpSseCommunicator."""
    # Create server and client agents
    server = SampleServerAgent()
    client = SampleClientAgent()

    server_task = None
    try:
        # Setup agents
        await server.setup()
        await client.setup()

        # Start server
        server_task = asyncio.create_task(server.run())

        # Allow server to start up
        await asyncio.sleep(2)

        # Call tools on the server
        add_result = await client.call_tool(
            target_service="sample_server",
            tool_name="add",
            arguments={"a": 5, "b": 7},
        )

        # Check result
        assert isinstance(add_result, dict)
        assert "sum" in add_result
        assert add_result["sum"] == 12
        assert "operation" in add_result
        assert add_result["operation"] == "Added 5 and 7"

        # Call another tool
        multiply_result = await client.call_tool(
            target_service="sample_server",
            tool_name="multiply",
            arguments={"a": 6, "b": 8},
        )

        # Check result
        assert isinstance(multiply_result, dict)
        assert "product" in multiply_result
        assert multiply_result["product"] == 48
        assert "operation" in multiply_result
        assert multiply_result["operation"] == "Multiplied 6 and 8"

        # Test dynamically adding a tool to the server
        async def subtract(a: int, b: int) -> Dict[str, Any]:
            """Subtract b from a."""
            return {"difference": a - b, "operation": f"Subtracted {b} from {a}"}

        # Add the tool to the server agent
        await server.add_tool(subtract, name="subtract", description="Subtract b from a")

        # Allow time for registration
        await asyncio.sleep(1)

        # Call the dynamically added tool
        subtract_result = await client.call_tool(
            target_service="sample_server",
            tool_name="subtract",
            arguments={"a": 20, "b": 8},
        )

        # Check result
        assert isinstance(subtract_result, dict)
        assert "difference" in subtract_result
        assert subtract_result["difference"] == 12
        assert "operation" in subtract_result
        assert subtract_result["operation"] == "Subtracted 8 from 20"

    finally:
        # Clean up
        if server_task:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

        # Shutdown agents
        await server.shutdown()
        await client.communicator.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(30)  # Timeout in seconds
async def test_agent_tool_registration() -> None:
    """Test that tools are correctly registered with the communicator during setup."""
    # Create server agent
    server = SampleServerAgent()

    try:
        # Start the communicator
        await server.communicator.start()

        # Setup the agent, which should register tools
        await server.setup()

        # Check that tools were registered with the communicator
        assert server.communicator.server is not None

        # Check if dynamic tool addition works
        async def new_tool(x: str) -> Dict[str, Any]:
            """A new tool added after initialization."""
            return {"result": f"Processed: {x}"}

        # Add the tool to the agent
        await server.add_tool(new_tool, name="process", description="Process a string")

        # Since we've manually started the communicator and server,
        # we don't need to start the agent.run() task

    finally:
        # Stop the communicator
        await server.communicator.stop()
