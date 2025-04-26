"""Fixtures for MCP unit tests."""

from unittest import mock

import pytest

# Import mcp_mocks module to avoid duplication
from tests.unit.communication.mcp.mcp_mocks import Context, MockClientSession, MockFastMCP, apply_mcp_mocks


@pytest.fixture
def mock_mcp_environment():
    """Set up mocked MCP environment.

    This fixture is a simpler version of the environment setup that applies
    the necessary mocks but doesn't create a communicator instance.
    """
    # Apply mocks to sys.modules
    apply_mcp_mocks()

    # Create basic mock objects
    mock_client_session = mock.AsyncMock(spec=MockClientSession)
    mock_context = Context("test-session")

    # Set up common return values
    mock_client_session.request = mock.AsyncMock(return_value={"result": "success"})
    mock_client_session.call_tool = mock.AsyncMock(return_value="mock-tool-result")
    mock_client_session.send_notification = mock.AsyncMock()

    # Set up tool list
    mock_tool1 = mock.MagicMock()
    mock_tool1.name = "tool1"
    mock_tool1.description = "Tool 1"
    mock_tool2 = mock.MagicMock()
    mock_tool2.name = "tool2"
    mock_tool2.description = "Tool 2"
    mock_client_session.list_tools = mock.AsyncMock(return_value=[mock_tool1, mock_tool2])

    # Yield the environment
    yield {
        "mock_session": mock_client_session,
        "mock_context": mock_context,
    }

    # No cleanup needed as the fixtures are created for each test


@pytest.fixture
def mock_sse_client():
    """Create a mock SSE client for testing."""

    # Create mock objects for the client
    mock_client_func = mock.MagicMock()
    mock_manager = mock.AsyncMock()
    mock_client_func.return_value = mock_manager

    # Set up read/write streams
    mock_read_stream = mock.AsyncMock()
    mock_write_stream = mock.AsyncMock()
    mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

    # Apply the patch
    with mock.patch("mcp.client.sse.sse_client", mock_client_func):
        yield {
            "mock_client": mock_client_func,
            "mock_manager": mock_manager,
            "mock_read_stream": mock_read_stream,
            "mock_write_stream": mock_write_stream,
        }


@pytest.fixture
def mock_stdio_client():
    """Create a mock stdio client for testing."""

    # Create mock objects for the client
    mock_client_func = mock.MagicMock()
    mock_manager = mock.AsyncMock()
    mock_client_func.return_value = mock_manager

    # Set up read/write streams
    mock_read_stream = mock.AsyncMock()
    mock_write_stream = mock.AsyncMock()
    mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

    # Apply the patch
    with mock.patch("mcp.client.stdio.stdio_client", mock_client_func):
        yield {
            "mock_client": mock_client_func,
            "mock_manager": mock_manager,
            "mock_read_stream": mock_read_stream,
            "mock_write_stream": mock_write_stream,
        }


@pytest.fixture
def mock_client_session():
    """Create a mock ClientSession for testing."""
    # Apply mocks to ensure MCP is properly mocked
    apply_mcp_mocks()

    # Create mock ClientSession
    mock_session = mock.AsyncMock(spec=MockClientSession)

    # Set up common return values
    mock_session.request = mock.AsyncMock(return_value={"result": "success"})
    mock_session.call_tool = mock.AsyncMock(return_value="mock-tool-result")
    mock_session.send_notification = mock.AsyncMock()
    mock_session.send_message = mock.AsyncMock(return_value="mock-message-id")

    # Mock the context manager
    mock_session.__aenter__ = mock.AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = mock.AsyncMock()

    # Apply the patch
    with mock.patch("mcp.client.session.ClientSession", return_value=mock_session):
        yield mock_session


@pytest.fixture
def mock_fastmcp():
    """Create a mock FastMCP server for testing."""
    # Apply mocks to ensure MCP is properly mocked
    apply_mcp_mocks()

    # Create mock FastMCP
    mock_server = mock.MagicMock(spec=MockFastMCP)
    mock_context = Context("test-session")
    mock_server.get_context.return_value = mock_context

    # Mock async methods
    mock_server.handle_message = mock.AsyncMock()
    mock_server.start = mock.AsyncMock()
    mock_server.stop = mock.AsyncMock()

    # Apply the patch
    with mock.patch("mcp.server.fastmcp.FastMCP", return_value=mock_server):
        yield mock_server
