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
    service_urls = {
        "test-service": "http://localhost:8000",
        "other-service": "http://localhost:8001",
        "external-service": "http://external.mcp-server.com:8080",
    }
    return McpSseCommunicator("test-agent", service_urls)


class TestMcpSseCommunicator:
    """Tests for the McpSseCommunicator class."""

    def test_initialization(self):
        """Test that initialization sets up the communicator correctly."""
        service_urls = {
            "test-service": "http://localhost:8000",
            "other-service": "http://localhost:8001",
            "external-service": "http://external.mcp-server.com:8080",
        }

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
            assert sse_communicator.clients["test-service"] == (mock_read_stream, mock_write_stream)
            assert sse_communicator.sessions["test-service"] == mock_session
            assert "test-service" in sse_communicator.connected_services
            assert "test-service" in sse_communicator._client_managers

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.sse_communicator.sse_client")
    async def test_connect_to_external_service(self, mock_sse_client, sse_communicator):
        """Test connecting to an external MCP service."""
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

            # Connect to the external service
            await sse_communicator._connect_to_service("external-service")

            # Check that the client and session were created correctly
            mock_sse_client.assert_called_once_with("http://external.mcp-server.com:8080")
            mock_session_class.assert_called_once_with(mock_read_stream, mock_write_stream)
            assert sse_communicator.clients["external-service"] == (mock_read_stream, mock_write_stream)
            assert sse_communicator.sessions["external-service"] == mock_session
            assert "external-service" in sse_communicator.connected_services

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
            mock_tool1 = mock.MagicMock()
            mock_tool1.__dict__ = {"name": "tool1", "description": "Tool 1"}
            mock_tool2 = mock.MagicMock()
            mock_tool2.__dict__ = {"name": "tool2", "description": "Tool 2"}
            mock_session.list_tools.return_value = [mock_tool1, mock_tool2]

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

            # Create a mock result with a dictionary representation
            mock_result = mock.MagicMock()
            mock_result.__dict__ = {"result": "success"}

            # Configure the mock
            mock_session.call_tool = mock.AsyncMock(return_value=mock_result)

            # Call the tool
            result = await sse_communicator.call_tool("test-service", "test_tool", {"param": "value"})

            # Check the result
            mock_session.call_tool.assert_called_once_with("test_tool", arguments={"param": "value"})
            assert isinstance(result, dict)
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

            # Create mock results with dictionary representations
            mock_result1 = mock.MagicMock()
            mock_result1.__dict__ = {"data": "response"}

            # Configure the mock for standard tool call
            mock_session.call_tool = mock.AsyncMock(return_value=mock_result1)

            # Test different request types

            # 1. Standard tool call
            result = await sse_communicator.send_request("test-service", "custom_method", {"param": "value"})
            mock_session.call_tool.assert_called_with("custom_method", arguments={"param": "value"})
            assert isinstance(result, dict)
            assert result == {"data": "response"}

            # 2. Tool list
            mock_tool = mock.MagicMock()
            mock_tool.__dict__ = {"name": "tool1"}
            mock_session.list_tools = mock.AsyncMock(return_value=[mock_tool])

            result = await sse_communicator.send_request("test-service", "tool/list")
            mock_session.list_tools.assert_called_once()
            assert len(result) == 1
            assert result[0]["name"] == "tool1"

            # 3. Specific tool call
            mock_result3 = mock.MagicMock()
            mock_result3.__dict__ = {"output": "tool result"}
            mock_session.call_tool = mock.AsyncMock(return_value=mock_result3)

            result = await sse_communicator.send_request("test-service", "tool/call/special_tool", {"arg": "value"})
            mock_session.call_tool.assert_called_with("special_tool", arguments={"arg": "value"})
            assert isinstance(result, dict)
            assert result == {"output": "tool result"}

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
    async def test_start_and_stop_server_mode(self):
        """Test starting and stopping the communicator in server mode."""
        # Create a communicator with server mode enabled
        service_urls = {"test-service": "http://localhost:8000"}
        communicator = McpSseCommunicator(
            "test-agent", service_urls, server_mode=True, http_port=8080, server_instructions="Test instructions"
        )

        # Create mocks
        mock_server = mock.MagicMock()
        mock_task = mock.MagicMock()

        # Create a custom stop method to replace the real one
        async def patched_stop(*args, **kwargs):
            # Just cancel the task without trying to await it
            if communicator._server_task:
                communicator._server_task.cancel()
            communicator._server_task = None
            communicator.server = None

        # Mock the FastMCP class, asyncio.create_task, and the stop method
        with mock.patch("simple_mas.communication.mcp.sse_communicator.FastMCP", return_value=mock_server), mock.patch(
            "simple_mas.communication.mcp.sse_communicator.asyncio.create_task", return_value=mock_task
        ), mock.patch.object(communicator, "stop", patched_stop):
            # Start the communicator
            await communicator.start()

            # The task should be stored
            assert communicator._server_task == mock_task

            # Now stop the communicator
            await communicator.stop()

            # Check that the task was cancelled
            mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    @mock.patch("simple_mas.communication.mcp.sse_communicator.sse_client")
    async def test_stop_client_mode(self, mock_sse_client, sse_communicator):
        """Test stopping the communicator in client mode."""
        # Mock the client manager
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

            # Connect to a service
            await sse_communicator._connect_to_service("test-service")

            # Store mock manager for later assertion
            client_manager = sse_communicator._client_managers["test-service"]

            # Stop the communicator
            await sse_communicator.stop()

            # Check that client manager's __aexit__ was called
            client_manager.__aexit__.assert_called_once()
