"""Tests for the MCP STDIO communicator."""

import subprocess
from unittest import mock

import pytest

# Import all modules at the top level
from openmas.communication.mcp import McpStdioCommunicator
from openmas.exceptions import ServiceNotFoundError
from openmas.logging import get_logger
from tests.unit.communication.mcp.mcp_mocks import apply_mcp_mocks

# Apply MCP mocks after imports
apply_mcp_mocks()

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
    @mock.patch("openmas.communication.mcp.stdio_communicator.stdio_client")
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
        with mock.patch("openmas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Connect to the service
            await stdio_communicator._connect_to_service("test-service")

            # Check that the client and session were created correctly
            mock_stdio_client.assert_called_once()
            mock_session_class.assert_called_once_with(mock_read_stream, mock_write_stream)
            assert stdio_communicator.clients["test-service"] == (mock_read_stream, mock_write_stream)
            assert stdio_communicator.sessions["test-service"] == mock_session

    @pytest.mark.asyncio
    @mock.patch("openmas.communication.mcp.stdio_communicator.stdio_client")
    @mock.patch("openmas.communication.mcp.stdio_communicator.os.path.exists", return_value=True)
    async def test_connect_to_external_service(self, mock_path_exists, mock_stdio_client, stdio_communicator):
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
        with mock.patch("openmas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Mock StdioServerParameters to capture its arguments
            with mock.patch("openmas.communication.mcp.stdio_communicator.StdioServerParameters") as mock_params_class:
                mock_params = mock.MagicMock()
                mock_params_class.return_value = mock_params

                # Connect to the external service
                await stdio_communicator._connect_to_service("external-service")

                # Verify that path.exists was called with the executable path
                mock_path_exists.assert_called_once_with("/path/to/external/executable")

                # Verify that StdioServerParameters was called with the right command
                mock_params_class.assert_called_once()
                params_args = mock_params_class.call_args[1]  # Get kwargs
                assert params_args.get("command") == "/path/to/external/executable"

                # Verify that stdio_client was called with the mocked parameters
                mock_stdio_client.assert_called_once_with(mock_params)

                # Check that the session and client were correctly created
                mock_session_class.assert_called_once_with(mock_read_stream, mock_write_stream)
                assert stdio_communicator.clients["external-service"] == (mock_read_stream, mock_write_stream)
                assert stdio_communicator.sessions["external-service"] == mock_session

    @pytest.mark.asyncio
    async def test_connect_to_invalid_service(self, stdio_communicator):
        """Test connecting to an invalid service."""
        with pytest.raises(ServiceNotFoundError):
            await stdio_communicator._connect_to_service("invalid-service")

    @pytest.mark.asyncio
    @mock.patch("openmas.communication.mcp.stdio_communicator.stdio_client")
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
        with mock.patch("openmas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
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
    @mock.patch("openmas.communication.mcp.stdio_communicator.stdio_client")
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
        with mock.patch("openmas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Create a mock result with a dictionary representation
            mock_result = mock.MagicMock()
            mock_result.__dict__ = {"result": "success"}

            # Configure the mock
            mock_session.call_tool = mock.AsyncMock(return_value=mock_result)

            # Call the tool
            result = await stdio_communicator.call_tool("test-service", "test_tool", {"param": "value"})

            # Check the result
            mock_session.call_tool.assert_called_once_with("test_tool", arguments={"param": "value"})
            assert isinstance(result, dict)
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    @mock.patch("openmas.communication.mcp.stdio_communicator.stdio_client")
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
        with mock.patch("openmas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Create mock results with dictionary representations
            mock_result1 = mock.MagicMock()
            mock_result1.__dict__ = {"data": "response"}

            # Configure the mock for standard tool call
            mock_session.call_tool = mock.AsyncMock(return_value=mock_result1)

            # Test different request types

            # 1. Standard tool call
            result = await stdio_communicator.send_request("test-service", "custom_method", {"param": "value"})
            mock_session.call_tool.assert_called_with("custom_method", arguments={"param": "value"})
            assert isinstance(result, dict)
            assert result == {"data": "response"}

            # 2. Tool list
            mock_tool = mock.MagicMock()
            mock_tool.__dict__ = {"name": "tool1"}
            mock_session.list_tools = mock.AsyncMock(return_value=[mock_tool])

            result = await stdio_communicator.send_request("test-service", "tool/list")
            mock_session.list_tools.assert_called_once()
            assert len(result) == 1
            assert result[0]["name"] == "tool1"

            # 3. Specific tool call
            mock_result3 = mock.MagicMock()
            mock_result3.__dict__ = {"output": "tool result"}
            mock_session.call_tool = mock.AsyncMock(return_value=mock_result3)

            result = await stdio_communicator.send_request("test-service", "tool/call/special_tool", {"arg": "value"})
            mock_session.call_tool.assert_called_with("special_tool", arguments={"arg": "value"})
            assert isinstance(result, dict)
            assert result == {"output": "tool result"}

    @pytest.mark.asyncio
    @mock.patch("openmas.communication.mcp.stdio_communicator.stdio_client")
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

        # Pre-add the client connection to avoid initialization errors
        stdio_communicator.clients["test-service"] = (mock_read_stream, mock_write_stream)
        stdio_communicator.sessions["test-service"] = mock_session
        stdio_communicator._client_managers["test-service"] = mock_manager

        # Mock ClientSession and asyncio.create_task
        with mock.patch("openmas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class, mock.patch(
            "openmas.communication.mcp.stdio_communicator.asyncio.create_task"
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
        with mock.patch("openmas.communication.mcp.stdio_communicator.FastMCP", return_value=mock_server), mock.patch(
            "openmas.communication.mcp.stdio_communicator.asyncio.create_task", return_value=mock_task
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
    @mock.patch("openmas.communication.mcp.stdio_communicator.stdio_client")
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
        with mock.patch("openmas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
            mock_session_class.return_value = mock_session

            # Connect to a service
            await stdio_communicator._connect_to_service("test-service")

            # Store mock manager for later assertion
            client_manager = stdio_communicator._client_managers["test-service"]

            # Stop the communicator
            await stdio_communicator.stop()

            # Check that client manager's __aexit__ was called
            client_manager.__aexit__.assert_called_once()
