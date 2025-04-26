"""Tests for MCP stdio communicator with proper mocks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import all modules at the top level
from openmas.communication.mcp import McpStdioCommunicator
from openmas.exceptions import CommunicationError, ServiceNotFoundError
from tests.unit.communication.mcp.mcp_mocks import apply_mcp_mocks

# Apply MCP mocks after imports
apply_mcp_mocks()


class MockProcess:
    """Mock subprocess.Process for testing."""

    def __init__(self, stdout=None, stdin=None, returncode=0):
        """Initialize the mock process.

        Args:
            stdout: Mock stdout stream
            stdin: Mock stdin stream
            returncode: Return code for the process
        """
        self.stdout = stdout
        self.stdin = stdin
        self.returncode = returncode
        self.terminated = False
        self.pid = 12345  # Add mock pid

    def terminate(self):
        """Terminate the process."""
        self.terminated = True

    def poll(self):
        """Poll the process."""
        return self.returncode


class TestMcpStdioCommunicator:
    """Test cases for the McpStdioCommunicator."""

    def setup_method(self):
        """Set up test environment before each test."""
        self.service_urls = {
            "test_service": "test_command",
            "stdio_service": "stdio:/path/to/executable",
        }
        self.agent_name = "test_agent"
        self.communicator = McpStdioCommunicator(
            agent_name=self.agent_name,
            service_urls=self.service_urls,
            server_mode=False,
        )

    def teardown_method(self):
        """Clean up after each test."""
        # Reset any mocks or states
        pass

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test that the communicator initializes with correct attributes."""
        # Assert initialization
        assert self.communicator.agent_name == self.agent_name
        assert self.communicator.service_urls == self.service_urls
        assert self.communicator.server_mode is False
        assert self.communicator.server_instructions is None
        assert self.communicator.subprocesses == {}
        assert self.communicator.clients == {}
        assert self.communicator.sessions == {}
        assert self.communicator._client_managers == {}
        assert self.communicator.handlers == {}
        assert self.communicator.server is None
        assert self.communicator._server_task is None

    @pytest.mark.asyncio
    async def test_connect_to_service(self):
        """Test connecting to a service by patching low-level components."""
        # Create mock streams and session
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        mock_session = AsyncMock()

        # Patch the _client_managers
        with patch.object(self.communicator, "_client_managers", {}):
            # Patch ClientSession class
            with patch("openmas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
                # Set up mock returns
                mock_session_class.return_value = mock_session

                # Create a mock context manager
                mock_context_manager = AsyncMock()
                mock_context_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

                # Setup to return our mock manager when stdio_client is called
                with patch(
                    "openmas.communication.mcp.stdio_communicator.stdio_client", return_value=mock_context_manager
                ):
                    # Call the method
                    await self.communicator._connect_to_service("test_service")

                    # Verify session was created with correct streams
                    mock_session_class.assert_called_once_with(mock_read_stream, mock_write_stream)

                    # Verify session was initialized
                    mock_session.initialize.assert_called_once()

                    # Verify client and session are stored
                    assert self.communicator.clients["test_service"] == (mock_read_stream, mock_write_stream)
                    assert self.communicator.sessions["test_service"] == mock_session

    @pytest.mark.asyncio
    async def test_connect_to_invalid_service(self):
        """Test connecting to a non-existent service."""
        with pytest.raises(ServiceNotFoundError):
            await self.communicator._connect_to_service("non_existent_service")

    @pytest.mark.asyncio
    async def test_connect_to_stdio_service(self):
        """Test connecting to a service with stdio:// protocol."""
        # Create mock streams and session
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        mock_session = AsyncMock()

        # Patch the _client_managers dictionary directly
        with patch.object(self.communicator, "_client_managers", {}):
            # Patch os.path.exists to return True
            with patch("os.path.exists", return_value=True) as mock_path_exists:
                # Patch ClientSession class
                with patch("openmas.communication.mcp.stdio_communicator.ClientSession") as mock_session_class:
                    # Set up mock returns
                    mock_session_class.return_value = mock_session

                    # Create a mock context manager
                    mock_context_manager = AsyncMock()
                    mock_context_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)

                    # Setup to return our mock manager when stdio_client is called
                    with patch(
                        "openmas.communication.mcp.stdio_communicator.stdio_client", return_value=mock_context_manager
                    ):
                        # Call the method
                        await self.communicator._connect_to_service("stdio_service")

                        # Verify path exists was called with the path from the stdio:// URL
                        mock_path_exists.assert_called_once_with("/path/to/executable")

                        # Verify session was created with correct streams
                        mock_session_class.assert_called_once_with(mock_read_stream, mock_write_stream)

                        # Verify session was initialized
                        mock_session.initialize.assert_called_once()

                        # Verify client and session are stored
                        assert self.communicator.clients["stdio_service"] == (mock_read_stream, mock_write_stream)
                        assert self.communicator.sessions["stdio_service"] == mock_session

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test handling connection failure."""
        # Patch stdio_client to directly raise an exception
        with patch(
            "openmas.communication.mcp.stdio_communicator.stdio_client", side_effect=Exception("Connection error")
        ):
            # Try to connect, expect exception
            with pytest.raises(CommunicationError):
                await self.communicator._connect_to_service("test_service")

    @pytest.mark.asyncio
    async def test_send_request(self):
        """Test sending a request to a service."""
        # Mock the communicator session
        mock_session = AsyncMock()
        # Use a standard method that doesn't hit special cases
        mock_session.call_tool.return_value = {"result": "test_result"}

        # Patch _connect_to_service to not actually connect
        with patch.object(self.communicator, "_connect_to_service", AsyncMock()) as mock_connect:
            # Set the session
            self.communicator.sessions = {"test_service": mock_session}

            # Send a request using a custom method (not one of the special case methods)
            result = await self.communicator.send_request(
                target_service="test_service",
                method="custom_method",
                params={"param": "value"},
            )

            # Verify connect was called
            mock_connect.assert_called_once_with("test_service")

            # Verify that session.call_tool was called (this is what happens for custom methods)
            mock_session.call_tool.assert_called_once_with("custom_method", arguments={"param": "value"})

            # Verify result
            assert result == {"result": "test_result"}

    @pytest.mark.asyncio
    async def test_call_tool(self):
        """Test calling a tool directly."""
        # Create mock session and response
        mock_session = AsyncMock()
        mock_session.call_tool.return_value = {"result": "tool_result"}

        # Apply patch to avoid actual connection
        with patch.object(self.communicator, "_connect_to_service", AsyncMock()) as mock_connect:
            # Set the session manually
            self.communicator.sessions = {"test_service": mock_session}

            # Call tool
            result = await self.communicator.call_tool(
                target_service="test_service", tool_name="test_tool", arguments={"arg1": "value1"}
            )

            # Verify connect was called
            mock_connect.assert_called_once_with("test_service")

            # Verify the session's call_tool was called with correct parameters
            mock_session.call_tool.assert_called_once_with("test_tool", arguments={"arg1": "value1"})

            # Verify result
            assert result == {"result": "tool_result"}

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test listing tools via send_request."""
        # Set up mock response
        mock_tools = [
            {"name": "tool1", "description": "Description 1"},
            {"name": "tool2", "description": "Description 2"},
        ]

        # Patch the send_request method
        with patch.object(self.communicator, "send_request", AsyncMock(return_value=mock_tools)) as mock_send_request:
            # List tools
            tools = await self.communicator.list_tools(target_service="test_service")

            # Verify send_request was called with correct parameters
            mock_send_request.assert_called_once_with("test_service", "tool/list")

            # Verify result
            assert tools == mock_tools

    @pytest.mark.asyncio
    async def test_get_prompt(self):
        """Test getting a prompt through send_request."""
        # Create mock response
        mock_response = "Prompt result"

        # Apply both patches to avoid connection and properly mock send_request
        with patch.object(self.communicator, "_connect_to_service", AsyncMock()):
            with patch.object(
                self.communicator, "send_request", AsyncMock(return_value=mock_response)
            ) as mock_send_request:
                # Get prompt
                result = await self.communicator.get_prompt(
                    target_service="test_service", prompt_name="test_prompt", arguments={"arg1": "value1"}
                )

                # Verify send_request was called with correct parameters
                mock_send_request.assert_called_once_with(
                    target_service="test_service",
                    method="prompt/get/test_prompt",
                    params={"arg1": "value1"},
                    timeout=None,
                )

                # Verify result
                assert result == mock_response

    @pytest.mark.asyncio
    @patch("mcp.client.stdio.stdio_client")
    async def test_read_resource(self, mock_stdio_client):
        """Test reading a resource from a service."""
        # Create a mock send_request method
        mock_response = {"mime_type": "text/plain", "content": "Resource content"}
        self.communicator.send_request = AsyncMock(return_value=mock_response)

        # Read resource
        resource_uri = "/test/resource"
        result = await self.communicator.read_resource(
            target_service="test_service", resource_uri=resource_uri, timeout=None
        )

        # Verify send_request was called with correct parameters
        self.communicator.send_request.assert_called_once_with(
            target_service="test_service", method="resource/read", params={"uri": resource_uri}, timeout=None
        )

        # Verify result
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_cleanup_client_manager(self):
        """Test cleanup of client managers and resources."""
        # Create mock objects
        mock_client_manager = AsyncMock()
        mock_process = MockProcess()
        mock_session = MagicMock()

        # Set up communicator state
        service_name = "test_service"
        self.communicator._client_managers[service_name] = mock_client_manager
        self.communicator.subprocesses[service_name] = mock_process
        self.communicator.clients[service_name] = (AsyncMock(), AsyncMock())
        self.communicator.sessions[service_name] = mock_session

        # Call cleanup
        await self.communicator._cleanup_client_manager(service_name)

        # Verify cleanup
        mock_client_manager.__aexit__.assert_called_once_with(None, None, None)
        assert service_name not in self.communicator._client_managers
        assert service_name not in self.communicator.clients
        assert service_name not in self.communicator.sessions
        assert service_name not in self.communicator.subprocesses
        assert mock_process.terminated is True
