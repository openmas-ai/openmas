"""Tests for the MCP STDIO communicator."""

import subprocess
from unittest import mock

import pytest

# Check if MCP module is available
try:
    import mcp  # noqa: F401

    from simple_mas.communication.mcp import McpStdioCommunicator

    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    pytest.skip("MCP module is not available", allow_module_level=True)

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
    service_urls = {"test-service": "python -m test_service", "other-service": "python -m other_service"}
    return McpStdioCommunicator("test-agent", service_urls)


class TestMcpStdioCommunicator:
    """Tests for the McpStdioCommunicator class."""

    def test_initialization(self):
        """Test that initialization sets up the communicator correctly."""
        service_urls = {"test-service": "python -m test_service", "other-service": "python -m other_service"}

        communicator = McpStdioCommunicator("test-agent", service_urls)

        assert communicator.agent_name == "test-agent"
        assert communicator.service_urls == service_urls
        assert communicator.server_mode is False
        assert communicator.clients == {}
        assert communicator.sessions == {}
        assert communicator.connected_services == set()
        assert communicator.handlers == {}
        assert communicator.subprocesses == {}

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_connect_to_service(self, mock_stdio_client, stdio_communicator, mock_popen):
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
            mock_session.initialize.assert_called_once_with(name="test-agent")
            assert stdio_communicator.clients["test-service"] == (mock_read_stream, mock_write_stream)
            assert stdio_communicator.sessions["test-service"] == mock_session
            assert "test-service" in stdio_communicator.connected_services
            assert "test-service" in stdio_communicator.subprocesses

    @pytest.mark.asyncio
    async def test_connect_to_invalid_service(self, stdio_communicator):
        """Test connecting to an invalid service."""
        with pytest.raises(ServiceNotFoundError):
            await stdio_communicator._connect_to_service("invalid-service")

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_list_tools(self, mock_stdio_client, stdio_communicator, mock_popen):
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
            tool1 = mock.MagicMock()
            tool1.model_dump.return_value = {"name": "tool1", "description": "Tool 1"}
            tool2 = mock.MagicMock()
            tool2.model_dump.return_value = {"name": "tool2", "description": "Tool 2"}
            mock_session.list_tools.return_value = [tool1, tool2]

            # Call list_tools
            tools = await stdio_communicator.list_tools("test-service")

            # Check the result
            assert len(tools) == 2
            assert tools[0]["name"] == "tool1"
            assert tools[1]["name"] == "tool2"

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_call_tool(self, mock_stdio_client, stdio_communicator, mock_popen):
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
            mock_session.call_tool.return_value = {"result": "success"}

            # Call the tool
            result = await stdio_communicator.call_tool("test-service", "test_tool", {"param": "value"})

            # Check the result
            mock_session.call_tool.assert_called_once_with("test_tool", {"param": "value"}, timeout=None)
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_send_request(self, mock_stdio_client, stdio_communicator, mock_popen):
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
            mock_session.call_tool.return_value = {"data": "response"}

            # Test different request types

            # 1. Standard tool call
            result = await stdio_communicator.send_request("test-service", "custom_method", {"param": "value"})
            mock_session.call_tool.assert_called_with("custom_method", {"param": "value"}, timeout=None)
            assert result == {"data": "response"}

            # 2. Tool list
            mock_tool = mock.MagicMock()
            mock_tool.model_dump.return_value = {"name": "tool1"}
            mock_session.list_tools.return_value = [mock_tool]

            result = await stdio_communicator.send_request("test-service", "tool/list")
            mock_session.list_tools.assert_called_once()
            assert result == {"tools": [{"name": "tool1"}]}

            # 3. Resource list
            mock_resource = mock.MagicMock()
            mock_resource.model_dump.return_value = {"uri": "test-uri"}
            mock_session.list_resources.return_value = [mock_resource]

            result = await stdio_communicator.send_request("test-service", "resource/list")
            mock_session.list_resources.assert_called_once()
            assert result == {"resources": [{"uri": "test-uri"}]}

            # 4. Resource read
            mock_session.read_resource.return_value = "resource content"

            result = await stdio_communicator.send_request("test-service", "resource/read", {"uri": "test-uri"})
            mock_session.read_resource.assert_called_once_with("test-uri")
            assert result == {"content": "resource content"}

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_send_notification(self, mock_stdio_client, stdio_communicator, mock_popen):
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
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_server")
    async def test_start_and_stop_server_mode(self, mock_stdio_server, stdio_communicator):
        """Test starting and stopping the communicator in server mode."""
        # Set server mode
        stdio_communicator.server_mode = True

        # Mock the server
        mock_server = mock.MagicMock()
        mock_stdio_server.return_value.__aenter__.return_value = mock_server

        # Start the server
        await stdio_communicator.start()

        # Check that the server was set up correctly
        mock_stdio_server.assert_called_once()
        assert stdio_communicator.server == mock_server

        # Directly mock the server's __aexit__ method
        stdio_communicator.server = mock.MagicMock()

        # Stop the server
        await stdio_communicator.stop()

        # Just check that server is None after stopping
        assert stdio_communicator.server is None

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.stdio_communicator.stdio_client")
    async def test_stop_client_mode(self, mock_stdio_client, stdio_communicator, mock_popen):
        """Test stopping the communicator in client mode."""
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

            # Connect to the service
            await stdio_communicator._connect_to_service("test-service")

            # Setup mock process
            mock_process = stdio_communicator.subprocesses["test-service"]

            # Stop the communicator
            await stdio_communicator.stop()

            # Check that the client manager was exited
            mock_manager.__aexit__.assert_called_once_with(None, None, None)

            # Check that the process was terminated
            mock_process.terminate.assert_called_once()

            # Check that the state was cleaned up
            assert stdio_communicator.clients == {}
            assert stdio_communicator._client_managers == {}
            assert stdio_communicator.subprocesses == {}
            assert stdio_communicator.connected_services == set()
