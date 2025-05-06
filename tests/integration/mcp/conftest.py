"""Configuration for MCP integration tests."""

from typing import AsyncGenerator, Tuple

import pytest

from openmas.agent import McpClientAgent, McpServerAgent

# Check for MCP dependencies
try:
    import mcp  # noqa: F401 - Import to ensure package is available

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

# Skip all tests in this module if MCP is not available
pytestmark = pytest.mark.skipif(not HAS_MCP, reason="MCP dependencies not installed")


# Add command line option to run real MCP tests
def pytest_addoption(parser):
    parser.addoption("--run-real-mcp", action="store_true", default=False, help="Run real MCP integration tests")


# Define markers for the module
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "mcp: mark a test as requiring MCP dependencies")
    config.addinivalue_line(
        "markers", "real_process: mark a test as requiring real process execution with actual dependencies"
    )
    config.addinivalue_line("markers", "mock: mark a test as using mock implementations without real dependencies")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-real-mcp"):
        skip_real = pytest.mark.skip(reason="need --run-real-mcp option to run")
        for item in items:
            # Check if the test is in the 'real' subdirectory
            # Use item.path which should be a pathlib.Path object
            try:
                # Check if 'real' is a parent directory within the 'mcp' test structure
                # Find the index of the 'mcp' part
                mcp_index = item.path.parts.index("mcp")
                # Check if the next part is 'real'
                if len(item.path.parts) > mcp_index + 1 and item.path.parts[mcp_index + 1] == "real":
                    item.add_marker(skip_real)
            except ValueError:
                # 'mcp' not in path, ignore
                pass
            # Also check for explicit marker if needed (optional, based on current usage)
            # elif item.get_closest_marker("real_process"):
            #     item.add_marker(skip_real)


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
