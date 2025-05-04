"""Tests for HTTP client functionality in the communicator."""

from unittest import mock

import httpx
import pytest
from pydantic import BaseModel

from openmas.communication import HttpCommunicator
from openmas.exceptions import (
    CommunicationError,
    MethodNotFoundError,
    RequestTimeoutError,
    ServiceNotFoundError,
    ValidationError,
)


class ResponseModel(BaseModel):
    """A test response model."""

    result: str
    value: int


class TestHttpClient:
    """Tests for the HTTP client functionality."""

    @pytest.mark.asyncio
    async def test_send_request_success(self, mock_httpx, communicator_config):
        """Test sending a request successfully."""
        mock_client = mock_httpx[1]

        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Mock the response with custom data
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "test-id",
            "result": {"result": "success", "value": 42},
        }
        mock_client.post.return_value = mock_response

        # Send a request
        result = await communicator.send_request("test-service", "test_method", {"param1": "value1"})

        # Check the result
        assert result == {"result": "success", "value": 42}

        # Check that the client was called correctly
        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args
        assert args[0] == communicator_config["service_urls"]["test-service"]
        assert "json" in kwargs
        assert kwargs["json"]["method"] == "test_method"
        assert kwargs["json"]["params"] == {"param1": "value1"}

    @pytest.mark.asyncio
    async def test_send_request_with_model(self, mock_httpx, communicator_config):
        """Test sending a request with a response model."""
        mock_client = mock_httpx[1]

        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Mock the response with custom data
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "test-id",
            "result": {"result": "success", "value": 42},
        }
        mock_client.post.return_value = mock_response

        # Send a request with a response model
        result = await communicator.send_request(
            "test-service", "test_method", {"param1": "value1"}, response_model=ResponseModel
        )

        # Check the result
        assert isinstance(result, ResponseModel)
        assert result.result == "success"
        assert result.value == 42

    @pytest.mark.asyncio
    async def test_send_request_service_not_found(self, mock_httpx, communicator_config):
        """Test sending a request to a non-existent service."""
        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Send a request to a non-existent service
        with pytest.raises(ServiceNotFoundError):
            await communicator.send_request("non-existent-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_method_not_found(self, mock_httpx, communicator_config):
        """Test sending a request for a non-existent method."""
        mock_client = mock_httpx[1]

        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Mock the response with error data
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "test-id",
            "error": {"code": -32601, "message": "Method 'non_existent_method' not found"},
        }
        mock_client.post.return_value = mock_response

        # Send a request for a non-existent method
        with pytest.raises(MethodNotFoundError):
            await communicator.send_request("test-service", "non_existent_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_error(self, mock_httpx, communicator_config):
        """Test sending a request that results in an error."""
        mock_client = mock_httpx[1]

        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Mock the response with error data
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "test-id",
            "error": {"code": -32603, "message": "Internal error"},
        }
        mock_client.post.return_value = mock_response

        # Send a request that results in an error
        with pytest.raises(CommunicationError):
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_http_error(self, mock_httpx, communicator_config):
        """Test sending a request that results in an HTTP error."""
        mock_client = mock_httpx[1]

        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Mock the response with error status
        mock_response = mock.MagicMock()
        mock_response.status_code = 500

        # Create an HTTP error and set it as the side effect for raise_for_status
        http_error = httpx.HTTPStatusError("HTTP Error 500", request=mock.MagicMock(), response=mock_response)
        mock_response.raise_for_status.side_effect = http_error

        mock_client.post.return_value = mock_response

        # Send a request that results in an HTTP error
        with pytest.raises(CommunicationError):
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_httpx, communicator_config):
        """Test sending a notification successfully."""
        mock_client = mock_httpx[1]

        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Send a notification
        await communicator.send_notification("test-service", "test_method", {"param1": "value1"})

        # Check that the client was called correctly
        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args
        assert args[0] == communicator_config["service_urls"]["test-service"]
        assert "json" in kwargs
        assert kwargs["json"]["method"] == "test_method"
        assert kwargs["json"]["params"] == {"param1": "value1"}
        assert "id" not in kwargs["json"]

    @pytest.mark.asyncio
    async def test_send_notification_service_not_found(self, mock_httpx, communicator_config):
        """Test sending a notification to a non-existent service."""
        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Send a notification to a non-existent service
        with pytest.raises(ServiceNotFoundError):
            await communicator.send_notification("non-existent-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_timeout_error(self, mock_httpx, communicator_config):
        """Test sending a request that times out."""
        mock_client = mock_httpx[1]

        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Mock a timeout exception
        mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")

        # Send a request that should time out
        with pytest.raises(RequestTimeoutError):
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_with_validation_error(self, mock_httpx, communicator_config):
        """Test sending a request with invalid data for the response model."""
        mock_client = mock_httpx[1]

        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Mock the response with data that won't validate
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "test-id",
            "result": {"wrong_field": "data", "another_field": 42},  # Missing required fields
        }
        mock_client.post.return_value = mock_response

        # Send a request with a response model that won't validate the response
        with pytest.raises(ValidationError):
            await communicator.send_request(
                "test-service", "test_method", {"param1": "value1"}, response_model=ResponseModel
            )

    @pytest.mark.asyncio
    async def test_send_request_missing_result(self, mock_httpx, communicator_config):
        """Test sending a request that returns a response without a result field."""
        mock_client = mock_httpx[1]

        communicator = HttpCommunicator(
            communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
        )

        # Mock the response with missing result field
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "test-id",
            # No "result" field
        }
        mock_client.post.return_value = mock_response

        # Send a request
        with pytest.raises(CommunicationError) as excinfo:
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

        assert "missing 'result'" in str(excinfo.value)
