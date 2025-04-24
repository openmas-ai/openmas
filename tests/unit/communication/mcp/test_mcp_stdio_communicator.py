"""Tests for the MCP STDIO communicator."""

import subprocess
from unittest import mock

import pytest

# Check if MCP module is available
try:
    # First, check basic import of the mcp package
    import mcp  # noqa: F401

    # Then try to import the McpStdioCommunicator class
    from simple_mas.communication.mcp import McpStdioCommunicator

    HAS_MCP = True
except ImportError as e:
    HAS_MCP = False
    # More descriptive skip reason with the actual import error
    pytest.skip(f"MCP module is not available: {e}", allow_module_level=True)

from simple_mas.exceptions import ServiceNotFoundError
from simple_mas.logging import get_logger

# Get logger for tests
test_logger = get_logger(__name__)


class MockProcess:
    """Mock subprocess for testing."""

    def __init__(self):
        """Initialize the mock process."""
        self.stdin = mock.MagicMock()
        self.stdout = mock.MagicMock()
        self.stderr = mock.MagicMock()
        self.terminate = mock.MagicMock()
        self.wait = mock.MagicMock()


@pytest.fixture
def mock_popen(monkeypatch):
    """Mock subprocess.Popen for testing."""
    mock_process = MockProcess()

    def mock_popen_fn(*args, **kwargs):
        return mock_process

    monkeypatch.setattr(subprocess, "Popen", mock_popen_fn)
    return mock_process


@pytest.fixture
def stdio_communicator():
    """Create a test MCP stdio communicator."""
    service_urls = {
        "test-service": "python -m test_service",
        "other-service": "python -m other_service",
        "external-service": "stdio:/path/to/external/executable",
    }
    return McpStdioCommunicator("test-agent", service_urls)


class TestMcpStdioCommunicator:
    """Tests for the McpStdioCommunicator class."""

    def test_initialization(self):
        """Test that initialization sets up the communicator correctly."""
        service_urls = {
            "test-service": "python -m test_service",
            "other-service": "python -m other_service",
            "external-service": "stdio:/path/to/external/executable",
        }

        communicator = McpStdioCommunicator("test-agent", service_urls)

        assert communicator.agent_name == "test-agent"
        assert communicator.service_urls == service_urls
        assert communicator.server_mode is False
        assert communicator.clients == {}
        assert communicator.sessions == {}
        assert communicator.subprocesses == {}
        assert communicator._client_managers == {}
        assert communicator.handlers == {}

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_connect_to_service(self, mock_stdio_client, stdio_communicator):
        """Test connecting to a service."""
        # Mock the client and session
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_stdio_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Connect to the service
            await stdio_communicator._connect_to_service("test-service")

            # Check that the client and session were created correctly
            mock_stdio_client.assert_called_once()
            mock_session_class.assert_called_once_with(mock_read_stream, mock_write_stream)
            assert stdio_communicator.clients["test-service"] == (mock_read_stream, mock_write_stream)
            assert stdio_communicator.sessions["test-service"] == mock_session

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_connect_to_external_service(self, mock_stdio_client, stdio_communicator):
        """Test connecting to an external service with stdio protocol."""
        # Mock the client and session
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_stdio_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Connect to the external service
            await stdio_communicator._connect_to_service("external-service")

            # Check that the client and session were created correctly with the right command
            mock_stdio_client.assert_called_once()
            args, kwargs = mock_stdio_client.call_args
            # Verify the command was correctly passed to stdio_client
            assert "/path/to/external/executable" in str(args) or "/path/to/external/executable" in str(kwargs)

            mock_session_class.assert_called_once_with(mock_read_stream, mock_write_stream)
            assert stdio_communicator.clients["external-service"] == (mock_read_stream, mock_write_stream)
            assert stdio_communicator.sessions["external-service"] == mock_session

    @pytest.mark.asyncio
    async def test_connect_to_invalid_service(self, stdio_communicator):
        """Test connecting to an invalid service."""
        with pytest.raises(ServiceNotFoundError):
            await stdio_communicator._connect_to_service("invalid-service")

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_list_tools(self, mock_stdio_client, stdio_communicator):
        """Test listing tools."""
        # Mock the client and streams
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_stdio_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Mock the tool list response
            mock_tool1 = mock.MagicMock()
            mock_tool1.__dict__ = {"name": "tool1", "description": "Tool 1"}
            mock_tool2 = mock.MagicMock()
            mock_tool2.__dict__ = {"name": "tool2", "description": "Tool 2"}
            mock_session.list_tools.return_value = [mock_tool1, mock_tool2]

            # Call list_tools
            tools = await stdio_communicator.list_tools("test-service")

            # Check the result
            assert len(tools) == 2
            assert tools[0]["name"] == "tool1"
            assert tools[1]["name"] == "tool2"

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_call_tool(self, mock_stdio_client, stdio_communicator):
        """Test calling a tool."""
        # Mock the client and streams
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_stdio_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Mock response with a __dict__ attribute
            mock_result = mock.MagicMock()
            mock_result.__dict__ = {"result": "success"}
            mock_session.call_tool.return_value = mock_result

            # Call the tool
            result = await stdio_communicator.call_tool("test-service", "test_tool", {"param": "value"})

            # Check the result
            mock_session.call_tool.assert_called_once_with("test_tool", {"param": "value"}, timeout=None)
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_send_request(self, mock_stdio_client, stdio_communicator):
        """Test sending a request."""
        # Mock the client manager and streams
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_stdio_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Create mock results with __dict__ attribute
            mock_result = mock.MagicMock()
            mock_result.__dict__ = {"data": "response"}
            mock_session.call_tool.return_value = mock_result

            # Test different request types

            # 1. Standard tool call
            result = await stdio_communicator.send_request("test-service", "custom_method", {"param": "value"})
            mock_session.call_tool.assert_called_with("custom_method", {"param": "value"}, timeout=None)
            assert result == {"data": "response"}

            # 2. Tool list
            mock_tool = mock.MagicMock()
            mock_tool.__dict__ = {"name": "tool1"}
            mock_session.list_tools.return_value = [mock_tool]

            result = await stdio_communicator.send_request("test-service", "tool/list")
            mock_session.list_tools.assert_called_once()
            assert len(result) == 1
            assert result[0]["name"] == "tool1"

            # 3. Specific tool call
            mock_tool_result = mock.MagicMock()
            mock_tool_result.__dict__ = {"output": "tool result"}
            mock_session.call_tool.return_value = mock_tool_result

            result = await stdio_communicator.send_request("test-service", "tool/call/special_tool", {"arg": "value"})
            mock_session.call_tool.assert_called_with("special_tool", {"arg": "value"}, timeout=None)
            assert result == {"output": "tool result"}

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_send_notification(self, mock_stdio_client, stdio_communicator):
        """Test sending a notification."""
        # Mock the client manager and streams
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_stdio_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession and asyncio.create_task
        with mock.patch(
            "simple_mas.communication.mcp.stdio_communicator.ClientSession"
        ) as mock_session_class, mock.patch(
            "simple_mas.communication.mcp.stdio_communicator.asyncio.create_task"
        ) as mock_create_task:
            mock_session_class.return_value = mock_session

            # Send notification
            await stdio_communicator.send_notification("test-service", "notify/event", {"data": "value"})

            # Check that create_task was called
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_handler(self, stdio_communicator):
        """Test registering a handler."""

        # Create a handler function
        async def test_handler(arg1, arg2):
            return {"result": arg1 + arg2}

        # Register the handler
        await stdio_communicator.register_handler("test_method", test_handler)

        # Check the handler was registered
        assert stdio_communicator.handlers["test_method"] == test_handler

    @pytest.mark.asyncio
    async def test_start_and_stop_server_mode(self):
        """Test starting and stopping the communicator in server mode."""
        # Create a communicator with server mode enabled
        service_urls = {"test-service": "python -m test_service"}
        communicator = McpStdioCommunicator(
            "test-agent", service_urls, server_mode=True, server_instructions="Test instructions"
        )

        # Mock FastMCP server
        mock_server = mock.MagicMock()
        mock_task = mock.AsyncMock()

        # Patch the required components
        with mock.patch(
            "simple_mas.communication.mcp.stdio_communicator.FastMCP", return_value=mock_server
        ), mock.patch("simple_mas.communication.mcp.stdio_communicator.asyncio.create_task", return_value=mock_task):
            # Start the communicator
            await communicator.start()

            # Check server was created and started
            assert communicator.server == mock_server
            assert communicator._server_task == mock_task

            # Stop the communicator
            await communicator.stop()

            # Check server was stopped
            mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_stop_client_mode(self, mock_stdio_client, stdio_communicator):
        """Test stopping the communicator in client mode."""
        # Mock the client manager
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_stdio_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Connect to a service
            await stdio_communicator._connect_to_service("test-service")

            # Store mock manager for later assertion
            client_manager = stdio_communicator._client_managers["test-service"]

            # Stop the communicator
            await stdio_communicator.stop()

            # Check that client manager's __aexit__ was called
            client_manager.__aexit__.assert_called_once()
