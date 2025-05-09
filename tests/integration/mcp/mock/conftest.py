"""Fixtures for MCP SSE integration tests with mocks."""

import logging
from typing import Any, Callable, Dict
from unittest.mock import AsyncMock, patch

import pytest

from openmas.communication.mcp.sse_communicator import McpSseCommunicator

logger = logging.getLogger(__name__)


@pytest.fixture
async def mcp_sse_test_harness() -> Dict[str, Any]:
    """Create a test harness for MCP SSE communicator tests.

    This fixture provides a server and client communicator for testing MCP SSE
    functionality with mocks.

    Returns:
        Dict containing:
            - server_communicator: The server's McpSseCommunicator
            - client_communicator: The client's McpSseCommunicator
            - registered_tools: Dict of tool names to functions
    """
    # Set up patchers
    fastmcp_patcher = patch("mcp.server.fastmcp.FastMCP")
    sse_client_patcher = patch("mcp.client.sse.sse_client")
    client_session_patcher = patch("mcp.client.session.ClientSession")

    # Start patchers
    fastmcp_patcher.start()
    sse_client_patcher.start()
    client_session_patcher.start()

    try:
        # Set up server and client communicators
        server_communicator = McpSseCommunicator(
            agent_name="test_server",
            service_urls={},
            server_mode=True,
            http_port=8765,  # Use a specific port for tests
            server_instructions="Test server for MCP SSE integration tests",
        )

        client_communicator = McpSseCommunicator(
            agent_name="test_client",
            service_urls={"test_server": "http://localhost:8765"},
            server_mode=False,
        )

        # Mock the _run_fastmcp_server method with an AsyncMock
        with patch.object(server_communicator, "_run_fastmcp_server", new_callable=AsyncMock):
            # Start the server
            await server_communicator.start()

            # Storage for registered tools
            registered_tools: Dict[str, Callable] = {}

            # Return the test harness
            return {
                "server_communicator": server_communicator,
                "client_communicator": client_communicator,
                "registered_tools": registered_tools,
            }

    finally:
        # Make sure patchers are stopped in teardown via yield_fixture's cleanup mechanism
        pytest.MonkeyPatch().undo()

        # Note: We're not calling server_communicator.stop() here because
        # the server might be needed throughout the test. Individual tests
        # can clean up if needed.
