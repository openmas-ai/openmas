"""Tests for the MCP base communicator."""

import asyncio
from unittest import mock

import pytest

# Check if MCP module is available
try:
    import mcp  # noqa: F401

    from simple_mas.communication.mcp.mcp_adapter import McpClientAdapter

    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    pytest.skip("MCP module is not available", allow_module_level=True)

from simple_mas.exceptions import CommunicationError, ServiceNotFoundError


class TestMcpCommunicator(McpClientAdapter):
    """A test implementation of the MCP client adapter."""

    def __init__(self, agent_name, service_urls):
        super().__init__(agent_name, service_urls)
        self.connected_services = set()
        self.sent_messages = []

    async def _connect_to_service(self, service_name):
        """Connect to a service."""
        if service_name not in self.service_urls:
            raise ServiceNotFoundError(f"Service '{service_name}' not found", target=service_name)

        self.connected_services.add(service_name)

    async def _send_message(self, message, target_service):
        """Send a message to a service."""
        self.sent_messages.append((target_service, message))


@pytest.fixture
def communicator():
    """Create a test MCP communicator."""
    service_urls = {"test-service": "http://localhost:8000", "other-service": "http://localhost:8001"}
    return TestMcpCommunicator("test-agent", service_urls)


class TestMcpClientAdapter:
    """Tests for the McpClientAdapter class."""

    def test_initialization(self):
        """Test that initialization sets up the communicator correctly."""
        service_urls = {"test-service": "http://localhost:8000", "other-service": "http://localhost:8001"}

        communicator = TestMcpCommunicator("test-agent", service_urls)

        assert communicator.agent_name == "test-agent"
        assert communicator.service_urls == service_urls
        assert communicator.handlers == {}
        assert communicator.request_futures == {}

    @pytest.mark.asyncio
    async def test_send_request(self, communicator):
        """Test sending a request successfully."""
        # Set up a future to resolve
        request_id = None

        async def mock_send_message(message, target_service):
            nonlocal request_id
            request_id = message["id"]
            communicator.sent_messages.append((target_service, message))

        # Override _send_message to capture the request ID
        communicator._send_message = mock_send_message

        # Start a task to send a request
        task = asyncio.create_task(communicator.send_request("test-service", "test_method", {"param1": "value1"}))

        # Give the task a chance to run
        await asyncio.sleep(0.1)

        # Verify the request was sent
        assert len(communicator.sent_messages) == 1
        target, message = communicator.sent_messages[0]
        assert target == "test-service"
        assert message["method"] == "test_method"
        assert message["params"] == {"param1": "value1"}

        # Create a response
        response_data = {"result": "success", "value": 42}

        # Simulate receiving a response
        await communicator.handle_message({"jsonrpc": "2.0", "id": request_id, "result": response_data})

        # Check the result
        result = await task
        assert result == response_data

    @pytest.mark.asyncio
    async def test_send_request_error(self, communicator):
        """Test sending a request that results in an error."""
        # Set up a future to resolve
        request_id = None

        async def mock_send_message(message, target_service):
            nonlocal request_id
            request_id = message["id"]
            communicator.sent_messages.append((target_service, message))

        # Override _send_message to capture the request ID
        communicator._send_message = mock_send_message

        # Start a task to send a request
        task = asyncio.create_task(communicator.send_request("test-service", "test_method", {"param1": "value1"}))

        # Give the task a chance to run
        await asyncio.sleep(0.1)

        # Simulate receiving an error response
        await communicator.handle_message(
            {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": "Internal error"}}
        )

        # Check that the task raised an exception
        with pytest.raises(CommunicationError):
            await task

    @pytest.mark.asyncio
    async def test_send_notification(self, communicator):
        """Test sending a notification successfully."""
        # Send a notification
        await communicator.send_notification("test-service", "test_method", {"param1": "value1"})

        # Verify the notification was sent
        assert len(communicator.sent_messages) == 1
        target, message = communicator.sent_messages[0]
        assert target == "test-service"
        assert message["method"] == "test_method"
        assert message["params"] == {"param1": "value1"}
        assert "id" not in message

    @pytest.mark.asyncio
    async def test_handle_message_response(self, communicator):
        """Test handling a response message."""
        # Create a future
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        request_id = "test-id"
        communicator.request_futures[request_id] = future

        # Handle a response message
        response = await communicator.handle_message(
            {"jsonrpc": "2.0", "id": request_id, "result": {"result": "success"}}
        )

        # Check that the future was resolved
        assert future.done()
        assert await future == {"result": "success"}
        assert response is None  # No response to a response

    @pytest.mark.asyncio
    async def test_handle_message_request(self, communicator):
        """Test handling a request message."""

        # Register a handler
        async def handler(params):
            return {"result": "success"}

        await communicator.register_handler("test_method", handler)

        # Handle a request message
        response = await communicator.handle_message(
            {"jsonrpc": "2.0", "id": "test-id", "method": "test_method", "params": {"param1": "value1"}}
        )

        # Check the response
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-id"
        assert response["result"] == {"result": "success"}

    @pytest.mark.asyncio
    async def test_handle_message_request_error(self, communicator):
        """Test handling a request message that raises an error."""

        # Register a handler that raises an exception
        async def handler(params):
            raise ValueError("Test error")

        await communicator.register_handler("test_method", handler)

        # Handle a request message
        response = await communicator.handle_message(
            {"jsonrpc": "2.0", "id": "test-id", "method": "test_method", "params": {"param1": "value1"}}
        )

        # Check the error response
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-id"
        assert "error" in response
        assert response["error"]["code"] == -32603
        assert "Test error" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_handle_message_notification(self, communicator):
        """Test handling a notification message."""
        # Register a handler
        handler = mock.AsyncMock()
        await communicator.register_handler("test_method", handler)

        # Handle a notification message
        response = await communicator.handle_message(
            {"jsonrpc": "2.0", "method": "test_method", "params": {"param1": "value1"}}
        )

        # Check that the handler was called
        handler.assert_called_once_with({"param1": "value1"})
        assert response is None  # No response to a notification

    @pytest.mark.asyncio
    async def test_handle_initialize_request(self, communicator):
        """Test handling an initialize request."""
        # Handle an initialize request
        response = await communicator.handle_message(
            {"jsonrpc": "2.0", "id": "test-id", "method": "initialize", "params": {"name": "client"}}
        )

        # Check the response
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "test-id"
        assert "result" in response
        assert response["result"]["name"] == "test-agent"
        assert "capabilities" in response["result"]

    @pytest.mark.asyncio
    async def test_handle_initialized_notification(self, communicator):
        """Test handling an initialized notification."""
        # Handle an initialized notification
        response = await communicator.handle_message({"jsonrpc": "2.0", "method": "initialized", "params": {}})

        # No response to a notification
        assert response is None
