"""Tests for the HTTP communicator."""

from unittest import mock

import httpx
import pytest
from pydantic import BaseModel

from openmas.communication import HttpCommunicator
from openmas.exceptions import CommunicationError, MethodNotFoundError, ServiceNotFoundError


class TestResponse:
    """A test response object to mock httpx responses."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self.reason_phrase = f"Status {status_code}"
        self._json_data = json_data or {}

    def json(self):
        """Return the JSON data."""
        return self._json_data

    def raise_for_status(self):
        """Raise an exception if the status code is not 2xx."""
        if 400 <= self.status_code < 600:
            raise httpx.HTTPStatusError(f"HTTP Error {self.status_code}", request=mock.MagicMock(), response=self)


class ResponseModel(BaseModel):
    """A test response model."""

    result: str
    value: int


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx client."""
    with mock.patch("httpx.AsyncClient", autospec=True) as mock_client_class:
        mock_client = mock.AsyncMock()
        mock_client_class.return_value = mock_client
        yield mock_client


class TestHttpCommunicator:
    """Tests for the HttpCommunicator class."""

    def test_initialization(self):
        """Test that initialization sets up the communicator correctly."""
        service_urls = {"test-service": "http://localhost:8000", "other-service": "http://localhost:8001"}

        communicator = HttpCommunicator("test-agent", service_urls)

        assert communicator.agent_name == "test-agent"
        assert communicator.service_urls == service_urls
        assert communicator.handlers == {}
        assert communicator.server_task is None

    @pytest.mark.asyncio
    async def test_send_request_success(self, mock_httpx_client):
        """Test sending a request successfully."""
        service_urls = {"test-service": "http://localhost:8000"}
        communicator = HttpCommunicator("test-agent", service_urls)

        # Mock the response
        mock_httpx_client.post.return_value = TestResponse(
            json_data={"jsonrpc": "2.0", "id": "test-id", "result": {"result": "success", "value": 42}}
        )

        # Send a request
        result = await communicator.send_request("test-service", "test_method", {"param1": "value1"})

        # Check the result
        assert result == {"result": "success", "value": 42}

        # Check that the client was called correctly
        mock_httpx_client.post.assert_called_once()
        args, kwargs = mock_httpx_client.post.call_args
        assert args[0] == "http://localhost:8000"
        assert "json" in kwargs
        assert kwargs["json"]["method"] == "test_method"
        assert kwargs["json"]["params"] == {"param1": "value1"}

    @pytest.mark.asyncio
    async def test_send_request_with_model(self, mock_httpx_client):
        """Test sending a request with a response model."""
        service_urls = {"test-service": "http://localhost:8000"}
        communicator = HttpCommunicator("test-agent", service_urls)

        # Mock the response
        mock_httpx_client.post.return_value = TestResponse(
            json_data={"jsonrpc": "2.0", "id": "test-id", "result": {"result": "success", "value": 42}}
        )

        # Send a request with a response model
        result = await communicator.send_request(
            "test-service", "test_method", {"param1": "value1"}, response_model=ResponseModel
        )

        # Check the result
        assert isinstance(result, ResponseModel)
        assert result.result == "success"
        assert result.value == 42

    @pytest.mark.asyncio
    async def test_send_request_service_not_found(self, mock_httpx_client):
        """Test sending a request to a non-existent service."""
        service_urls = {"test-service": "http://localhost:8000"}
        communicator = HttpCommunicator("test-agent", service_urls)

        # Send a request to a non-existent service
        with pytest.raises(ServiceNotFoundError):
            await communicator.send_request("non-existent-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_method_not_found(self, mock_httpx_client):
        """Test sending a request for a non-existent method."""
        service_urls = {"test-service": "http://localhost:8000"}
        communicator = HttpCommunicator("test-agent", service_urls)

        # Mock the response
        mock_httpx_client.post.return_value = TestResponse(
            json_data={
                "jsonrpc": "2.0",
                "id": "test-id",
                "error": {"code": -32601, "message": "Method 'non_existent_method' not found"},
            }
        )

        # Send a request for a non-existent method
        with pytest.raises(MethodNotFoundError):
            await communicator.send_request("test-service", "non_existent_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_error(self, mock_httpx_client):
        """Test sending a request that results in an error."""
        service_urls = {"test-service": "http://localhost:8000"}
        communicator = HttpCommunicator("test-agent", service_urls)

        # Mock the response
        mock_httpx_client.post.return_value = TestResponse(
            json_data={"jsonrpc": "2.0", "id": "test-id", "error": {"code": -32603, "message": "Internal error"}}
        )

        # Send a request that results in an error
        with pytest.raises(CommunicationError):
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_http_error(self, mock_httpx_client):
        """Test sending a request that results in an HTTP error."""
        service_urls = {"test-service": "http://localhost:8000"}
        communicator = HttpCommunicator("test-agent", service_urls)

        # Mock the response
        mock_httpx_client.post.return_value = TestResponse(status_code=500)

        # Send a request that results in an HTTP error
        with pytest.raises(CommunicationError):
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_httpx_client):
        """Test sending a notification successfully."""
        service_urls = {"test-service": "http://localhost:8000"}
        communicator = HttpCommunicator("test-agent", service_urls)

        # Mock the response
        mock_httpx_client.post.return_value = TestResponse()

        # Send a notification
        await communicator.send_notification("test-service", "test_method", {"param1": "value1"})

        # Check that the client was called correctly
        mock_httpx_client.post.assert_called_once()
        args, kwargs = mock_httpx_client.post.call_args
        assert args[0] == "http://localhost:8000"
        assert "json" in kwargs
        assert kwargs["json"]["method"] == "test_method"
        assert kwargs["json"]["params"] == {"param1": "value1"}
        assert "id" not in kwargs["json"]

    @pytest.mark.asyncio
    async def test_register_handler(self):
        """Test registering a handler."""
        communicator = HttpCommunicator("test-agent", {})

        # Define a handler
        async def handler(params):
            return {"result": "success"}

        # Register the handler
        await communicator.register_handler("test_method", handler)

        # Check that the handler was registered
        assert "test_method" in communicator.handlers
        assert communicator.handlers["test_method"] == handler

    @pytest.mark.asyncio
    async def test_lifecycle(self, mock_httpx_client):
        """Test the communicator lifecycle."""
        communicator = HttpCommunicator("test-agent", {})

        # Start the communicator
        await communicator.start()

        # Stop the communicator
        await communicator.stop()

        # Check that the client was closed
        mock_httpx_client.aclose.assert_called_once()
