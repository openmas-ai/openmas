"""Integration tests for MCP SDK v1.6.

This module provides a minimal test to verify that the MCP SDK v1.6 is available
and can be instantiated. This is a very basic integration test to verify the
dependency is installed and functioning.
"""

import pytest
from mcp.server.fastmcp import FastMCP

# Mark all tests in this module with the 'mcp' marker
pytestmark = [
    pytest.mark.mcp,
]


def test_mcp_minimal_integration() -> None:
    """Test minimal MCP functionality.

    This test simply verifies we can:
    1. Import the MCP SDK
    2. Create a FastMCP instance
    """
    # Create a FastMCP server instance
    app = FastMCP("TestServer")

    # Register a tool using the decorator (just verify it doesn't error)
    @app.tool()
    async def echo(message: str) -> str:
        """Echo back the input message."""
        return message

    # Success - we were able to import and use the SDK
