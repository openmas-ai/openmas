"""Configuration for MCP integration tests."""

from typing import AsyncGenerator, Tuple

import pytest

from openmas.agent import McpClientAgent, McpServerAgent

# Try importing necessary MCP dependencies, and skip the tests if they're not available
try:
    import mcp  # noqa: F401 - Import to ensure package is available

    # Imports actually used by test files, but imported here for module-level skip logic
except ImportError:
    pytest.skip("MCP dependencies not installed", allow_module_level=True)

pytestmark = pytest.mark.mcp


@pytest.fixture
async def mcp_server_client_pair() -> AsyncGenerator[Tuple[McpServerAgent, McpClientAgent], None]:
    """Create a pair of MCP server and client agents for testing.

    Both agents use in-memory communication for testing purposes.

    Yields:
        Tuple[McpServerAgent, McpClientAgent]: A tuple containing the server and client agents
    """
    # Create a server agent
    server = McpServerAgent(
        name="test_server",
        config={
            "COMMUNICATOR_TYPE": "mcp-sse",
            "SERVER_MODE": True,
            "HTTP_PORT": 8765,  # Use a specific port for tests
            "SERVER_INSTRUCTIONS": "Test MCP server for integration tests",
        },
    )

    # Create a client agent
    client = McpClientAgent(
        name="test_client",
        config={"COMMUNICATOR_TYPE": "mcp-sse", "SERVICE_URLS": {"test_server": "http://localhost:8765"}},
    )

    # Start the server agent
    await server.start()

    try:
        # Start the client agent
        await client.start()

        # Yield the pair for testing
        yield server, client
    finally:
        # Clean up
        await client.stop()
        await server.stop()
