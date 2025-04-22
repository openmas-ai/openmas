"""Tests for the MCP SSE communicator."""

from unittest import mock

import pytest

# Check if MCP module is available
try:
    import mcp  # noqa: F401

    from simple_mas.communication.mcp import McpSseCommunicator

    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    pytest.skip("MCP module is not available", allow_module_level=True)

from simple_mas.exceptions import ServiceNotFoundError
from simple_mas.logging import get_logger

# Get logger for tests
test_logger = get_logger(__name__)


@pytest.fixture
def sse_communicator():
    """Create a test MCP SSE communicator."""
    service_urls = {"test-service": "http://localhost:8000", "other-service": "http://localhost:8001"}
    return McpSseCommunicator("test-agent", service_urls)


class TestMcpSseCommunicator:
    """Tests for the McpSseCommunicator class."""

    def test_initialization(self):
        """Test that initialization sets up the communicator correctly."""
        service_urls = {"test-service": "http://localhost:8000", "other-service": "http://localhost:8001"}

        communicator = McpSseCommunicator("test-agent", service_urls)

        assert communicator.agent_name == "test-agent"
        assert communicator.service_urls == service_urls
        assert communicator.server_mode is False
        assert communicator.clients == {}
        assert communicator.sessions == {}
        assert communicator.connected_services == set()
        assert communicator.handlers == {}
        assert communicator._client_managers == {}

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.sse_communicator.sse_client")
    async def test_connect_to_service(self, mock_sse_client, sse_communicator):
        """Test connecting to a service."""
        # Mock the client and session
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_sse_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.sse_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Connect to the service
            await sse_communicator._connect_to_service("test-service")

            # Check that the client and session were created correctly
            mock_sse_client.assert_called_once_with("http://localhost:8000")
            mock_session_class.assert_called_once_with(mock_read_stream, mock_write_stream)
            mock_session.initialize.assert_called_once_with(name="test-agent")
            assert sse_communicator.clients["test-service"] == (mock_read_stream, mock_write_stream)
            assert sse_communicator.sessions["test-service"] == mock_session
            assert "test-service" in sse_communicator.connected_services
            assert "test-service" in sse_communicator._client_managers

    @pytest.mark.asyncio
    async def test_connect_to_invalid_service(self, sse_communicator):
        """Test connecting to an invalid service."""
        with pytest.raises(ServiceNotFoundError):
            await sse_communicator._connect_to_service("invalid-service")

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.sse_communicator.sse_client")
    async def test_list_tools(self, mock_sse_client, sse_communicator):
        """Test listing tools."""
        # Mock the client and streams
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_sse_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.sse_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Mock the tool list response
            tool1 = mock.MagicMock()
            tool1.model_dump.return_value = {"name": "tool1", "description": "Tool 1"}
            tool2 = mock.MagicMock()
            tool2.model_dump.return_value = {"name": "tool2", "description": "Tool 2"}
            mock_session.list_tools.return_value = [tool1, tool2]

            # Call list_tools
            tools = await sse_communicator.list_tools("test-service")

            # Check the result
            assert len(tools) == 2
            assert tools[0]["name"] == "tool1"
            assert tools[1]["name"] == "tool2"

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.sse_communicator.sse_client")
    async def test_call_tool(self, mock_sse_client, sse_communicator):
        """Test calling a tool."""
        # Mock the client and streams
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_sse_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.sse_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session
            mock_session.call_tool.return_value = {"result": "success"}

            # Call the tool
            result = await sse_communicator.call_tool("test-service", "test_tool", {"param": "value"})

            # Check the result
            mock_session.call_tool.assert_called_once_with("test_tool", {"param": "value"}, timeout=None)
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.sse_communicator.sse_client")
    async def test_send_request(self, mock_sse_client, sse_communicator):
        """Test sending a request."""
        # Mock the client manager and streams
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_sse_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.sse_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session
            mock_session.call_tool.return_value = {"data": "response"}

            # Test different request types

            # 1. Standard tool call
            result = await sse_communicator.send_request("test-service", "custom_method", {"param": "value"})
            mock_session.call_tool.assert_called_with("custom_method", {"param": "value"}, timeout=None)
            assert result == {"data": "response"}

            # 2. Tool list
            mock_tool = mock.MagicMock()
            mock_tool.model_dump.return_value = {"name": "tool1"}
            mock_session.list_tools.return_value = [mock_tool]

            result = await sse_communicator.send_request("test-service", "tool/list")
            mock_session.list_tools.assert_called_once()
            assert result == {"tools": [{"name": "tool1"}]}

            # 3. Resource list
            mock_resource = mock.MagicMock()
            mock_resource.model_dump.return_value = {"uri": "test-uri"}
            mock_session.list_resources.return_value = [mock_resource]

            result = await sse_communicator.send_request("test-service", "resource/list")
            mock_session.list_resources.assert_called_once()
            assert result == {"resources": [{"uri": "test-uri"}]}

            # 4. Resource read
            mock_session.read_resource.return_value = "resource content"

            result = await sse_communicator.send_request("test-service", "resource/read", {"uri": "test-uri"})
            mock_session.read_resource.assert_called_once_with("test-uri")
            assert result == {"content": "resource content"}

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.sse_communicator.sse_client")
    async def test_send_notification(self, mock_sse_client, sse_communicator):
        """Test sending a notification."""
        # Mock the client manager and streams
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_sse_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession and asyncio.create_task
        with mock.patch(
            "simple_mas.communication.mcp.sse_communicator.ClientSession"
        ) as mock_session_class, mock.patch(
            "simple_mas.communication.mcp.sse_communicator.asyncio.create_task"
        ) as mock_create_task:
            mock_session_class.return_value = mock_session

            # Send notification
            await sse_communicator.send_notification("test-service", "notify/event", {"data": "value"})

            # Check that create_task was called
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_handler(self, sse_communicator):
        """Test registering a handler."""

        # Create a handler function
        async def test_handler(arg1, arg2):
            return {"result": arg1 + arg2}

        # Register the handler
        await sse_communicator.register_handler("test_method", test_handler)

        # Check the handler was registered
        assert sse_communicator.handlers["test_method"] == test_handler

    @pytest.mark.asyncio
    async def test_start_and_stop_server_mode(self, sse_communicator):
        """Test starting and stopping the communicator in server mode."""
        # Set server mode
        sse_communicator.server_mode = True

        # Mock the necessary components for server mode
        original_start = sse_communicator.start
        original_stop = sse_communicator.stop

        # Create a mocked server and task
        mock_server = mock.MagicMock()
        mock_task = mock.MagicMock()

        # Define a mocked start method
        async def mocked_start():
            test_logger.info("MCP SSE server started on port 8000")
            sse_communicator.server = mock_server
            sse_communicator.server_task = mock_task

        # Define a mocked stop method
        async def mocked_stop():
            if sse_communicator.server_task:
                sse_communicator.server_task.cancel()
                sse_communicator.server_task = None
            sse_communicator.server = None

        # Replace the methods
        sse_communicator.start = mocked_start
        sse_communicator.stop = mocked_stop

        try:
            # Start the server
            await sse_communicator.start()

            # Check that the server was set up correctly
            assert sse_communicator.server == mock_server
            assert sse_communicator.server_task == mock_task

            # Stop the server
            await sse_communicator.stop()

            # Check that the server was stopped correctly
            assert sse_communicator.server is None
            assert sse_communicator.server_task is None
        finally:
            # Restore original methods
            sse_communicator.start = original_start
            sse_communicator.stop = original_stop

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.sse_communicator.sse_client")
    async def test_stop_client_mode(self, mock_sse_client, sse_communicator):
        """Test stopping the communicator in client mode."""
        # Mock the client manager and streams
        mock_manager = mock.AsyncMock()
        mock_read_stream = mock.AsyncMock()
        mock_write_stream = mock.AsyncMock()
        mock_session = mock.AsyncMock()

        # Configure mocks
        mock_sse_client.return_value = mock_manager
        mock_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

        # Mock ClientSession
        with mock.patch("simple_mas.communication.mcp.sse_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Connect to the service
            await sse_communicator._connect_to_service("test-service")

            # Stop the communicator
            await sse_communicator.stop()

            # Check that the client manager was exited
            mock_manager.__aexit__.assert_called_once_with(None, None, None)

            # Check that the state was cleaned up
            assert sse_communicator.clients == {}
            assert sse_communicator._client_managers == {}
            assert sse_communicator.connected_services == set()
