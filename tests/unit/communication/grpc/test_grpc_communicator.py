"""Tests for the gRPC communicator."""

import asyncio
import json
import time
import uuid
from unittest import mock

import grpc
import pytest
from pydantic import BaseModel

from simple_mas.communication.grpc import GrpcCommunicator
from simple_mas.communication.grpc import simple_mas_pb2 as pb2
from simple_mas.communication.grpc.communicator import SimpleMasServicer
from simple_mas.exceptions import CommunicationError, MethodNotFoundError, RequestTimeoutError, ServiceNotFoundError


# Create a custom mock RpcError for testing
class MockRpcError(Exception):
    """Mock RpcError for testing."""

    def __init__(self, details="Mock RPC Error", code=grpc.StatusCode.UNKNOWN):
        self._code = code
        self._details = details
        super().__init__(details)

    def code(self):
        return self._code

    def details(self):
        return self._details


class ResponseModel(BaseModel):
    """A test response model."""

    result: str
    value: int


@pytest.fixture
def mock_grpc_channel():
    """Create a mock gRPC channel."""
    with mock.patch("grpc.aio.insecure_channel", autospec=True) as mock_channel_func:
        mock_channel = mock.AsyncMock()
        mock_channel_func.return_value = mock_channel
        yield mock_channel


@pytest.fixture
def mock_grpc_server():
    """Create a mock gRPC server."""
    with mock.patch("grpc.aio.server", autospec=True) as mock_server_func:
        yield mock_server_func


@pytest.fixture
def mock_grpc_stub():
    """Create a mock gRPC stub."""
    # Create stub with actual method names (uppercase first letter)
    mock_stub = mock.AsyncMock()

    # Setup mock response for SendRequest
    mock_response = mock.MagicMock(spec=pb2.ResponseMessage)
    mock_response.id = str(uuid.uuid4())
    mock_response.source = "test-service"
    mock_response.target = "test-agent"
    mock_response.result = json.dumps({"result": "success", "value": 42}).encode()

    # Create error attribute properly
    mock_error = mock.MagicMock()
    mock_error.code = 0
    mock_error.message = ""
    mock_error.details = ""
    mock_response.error = mock_error

    mock_response.timestamp = int(time.time() * 1000)

    mock_stub.SendRequest = mock.AsyncMock(return_value=mock_response)

    # Setup mock response for SendNotification
    mock_empty = mock.MagicMock(spec=pb2.Empty)
    mock_stub.SendNotification = mock.AsyncMock(return_value=mock_empty)

    return mock_stub


@pytest.fixture
def test_servicer():
    """Create a SimpleMasServicer for testing."""
    communicator = mock.AsyncMock(spec=GrpcCommunicator)
    communicator.agent_name = "test-agent"
    communicator.handlers = {}
    servicer = SimpleMasServicer(communicator)
    return servicer, communicator


class TestGrpcCommunicator:
    """Tests for the GrpcCommunicator class."""

    def test_initialization(self):
        """Test that initialization sets up the communicator correctly."""
        service_urls = {"test-service": "localhost:50051", "other-service": "localhost:50052"}

        communicator = GrpcCommunicator("test-agent", service_urls, server_address="[::]:50053")

        assert communicator.agent_name == "test-agent"
        assert communicator.service_urls == service_urls
        assert communicator.server_address == "[::]:50053"
        assert communicator.server_mode is False
        assert communicator.handlers == {}
        assert communicator.server is None
        assert communicator.servicer is None

    @pytest.mark.asyncio
    async def test_send_request_success(self, mock_grpc_channel, mock_grpc_stub):
        """Test sending a request successfully."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_grpc_stub)

        # Send a request
        result = await communicator.send_request("test-service", "test_method", {"param1": "value1"})

        # Check the result
        assert result == {"result": "success", "value": 42}

        # Check that the stub was called correctly
        mock_grpc_stub.SendRequest.assert_called_once()
        args, kwargs = mock_grpc_stub.SendRequest.call_args
        request = args[0]
        assert request.source == "test-agent"
        assert request.target == "test-service"
        assert request.method == "test_method"
        assert json.loads(request.params) == {"param1": "value1"}

    @pytest.mark.asyncio
    async def test_send_request_with_model(self, mock_grpc_channel):
        """Test sending a request with a response model."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Create a mock response
        mock_response = mock.MagicMock(spec=pb2.ResponseMessage)
        mock_response.id = str(uuid.uuid4())
        mock_response.source = "test-service"
        mock_response.target = "test-agent"
        mock_response.result = json.dumps({"result": "success", "value": 42}).encode()

        # Create error attribute properly
        mock_error = mock.MagicMock()
        mock_error.code = 0
        mock_error.message = ""
        mock_error.details = ""
        mock_response.error = mock_error

        mock_response.timestamp = int(time.time() * 1000)

        # Mock the stub with correct method name
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(return_value=mock_response)

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Send a request with a response model
        result = await communicator.send_request(
            "test-service", "test_method", {"param1": "value1"}, response_model=ResponseModel
        )

        # Check the result
        assert isinstance(result, ResponseModel)
        assert result.result == "success"
        assert result.value == 42

    @pytest.mark.asyncio
    async def test_send_request_service_not_found(self):
        """Test sending a request to a non-existent service."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Send a request to a non-existent service
        with pytest.raises(ServiceNotFoundError):
            await communicator.send_request("non-existent-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_method_not_found(self, mock_grpc_channel):
        """Test sending a request for a non-existent method."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Create a mock response with method not found error
        mock_response = mock.MagicMock(spec=pb2.ResponseMessage)
        mock_response.id = str(uuid.uuid4())
        mock_response.source = "test-service"
        mock_response.target = "test-agent"
        mock_response.result = b""

        # Create error attribute properly
        mock_error = mock.MagicMock()
        mock_error.code = 404
        mock_error.message = "Method not found"
        mock_error.details = "MethodNotFoundError"
        mock_response.error = mock_error

        mock_response.timestamp = int(time.time() * 1000)

        # Mock the stub with correct method name
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(return_value=mock_response)

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Send a request for a non-existent method
        with pytest.raises(MethodNotFoundError):
            await communicator.send_request("test-service", "non_existent_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_error(self, mock_grpc_channel):
        """Test sending a request that results in an error."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Create a mock response with a generic error
        mock_response = mock.MagicMock(spec=pb2.ResponseMessage)
        mock_response.id = str(uuid.uuid4())
        mock_response.source = "test-service"
        mock_response.target = "test-agent"
        mock_response.result = b""

        # Create error attribute properly
        mock_error = mock.MagicMock()
        mock_error.code = 500
        mock_error.message = "Internal error"
        mock_error.details = "InternalError"
        mock_response.error = mock_error

        mock_response.timestamp = int(time.time() * 1000)

        # Mock the stub with correct method name
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(return_value=mock_response)

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Send a request that results in an error
        with pytest.raises(CommunicationError):
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_grpc_error(self, mock_grpc_channel):
        """Test sending a request that results in a gRPC error."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Mock the stub with correct method name
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(side_effect=MockRpcError("General RPC error"))

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Send a request that results in a gRPC error
        with pytest.raises(CommunicationError):
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_timeout(self, mock_grpc_channel):
        """Test sending a request that times out due to gRPC DEADLINE_EXCEEDED."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Create a proper mock RpcError with DEADLINE_EXCEEDED status code
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(
            side_effect=MockRpcError("Deadline exceeded", grpc.StatusCode.DEADLINE_EXCEEDED)
        )

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Send a request with a timeout
        with pytest.raises(RequestTimeoutError):
            await communicator.send_request("test-service", "test_method", {"param1": "value1"}, timeout=1.0)

    @pytest.mark.asyncio
    async def test_send_request_asyncio_timeout(self, mock_grpc_channel):
        """Test sending a request that times out due to asyncio.TimeoutError."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Mock the stub with correct method name
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(side_effect=asyncio.TimeoutError())

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Send a request with a timeout
        with pytest.raises(RequestTimeoutError):
            await communicator.send_request("test-service", "test_method", {"param1": "value1"}, timeout=1.0)

    @pytest.mark.asyncio
    async def test_error_mapping(self, mock_grpc_channel):
        """Test mapping of gRPC status codes to SimpleMasError types."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Create a dict of error codes and expected exception types
        error_mapping = [
            (404, MethodNotFoundError),
            (408, RequestTimeoutError),
            (500, CommunicationError),
        ]

        for error_code, expected_exception in error_mapping:
            # Create a mock response with the specific error
            mock_response = mock.MagicMock(spec=pb2.ResponseMessage)
            mock_response.id = str(uuid.uuid4())
            mock_response.source = "test-service"
            mock_response.target = "test-agent"
            mock_response.result = b""

            # Create error attribute properly
            mock_error = mock.MagicMock()
            mock_error.code = error_code
            mock_error.message = f"Error with code {error_code}"
            mock_error.details = "ErrorDetails"
            mock_response.error = mock_error

            mock_response.timestamp = int(time.time() * 1000)

            # Mock the stub with correct method name
            mock_stub = mock.AsyncMock()
            mock_stub.SendRequest = mock.AsyncMock(return_value=mock_response)

            # Mock the stub getter
            communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

            # Send a request that should result in the expected exception
            with pytest.raises(expected_exception):
                await communicator.send_request("test-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_grpc_channel, mock_grpc_stub):
        """Test sending a notification successfully."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_grpc_stub)

        # Send a notification
        await communicator.send_notification("test-service", "test_method", {"param1": "value1"})

        # Check that the stub was called correctly
        mock_grpc_stub.SendNotification.assert_called_once()
        args, kwargs = mock_grpc_stub.SendNotification.call_args
        notification = args[0]
        assert notification.source == "test-agent"
        assert notification.target == "test-service"
        assert notification.method == "test_method"
        assert json.loads(notification.params) == {"param1": "value1"}

    @pytest.mark.asyncio
    async def test_send_notification_service_not_found(self):
        """Test sending a notification to a non-existent service."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Send a notification to a non-existent service
        with pytest.raises(ServiceNotFoundError):
            await communicator.send_notification("non-existent-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_notification_error(self, mock_grpc_channel):
        """Test sending a notification that results in an error."""
        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Mock the stub with correct method name
        mock_stub = mock.AsyncMock()
        mock_stub.SendNotification = mock.AsyncMock(side_effect=MockRpcError("General RPC error"))

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Send a notification that results in an error
        with pytest.raises(CommunicationError):
            await communicator.send_notification("test-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_register_handler(self):
        """Test registering a handler."""
        communicator = GrpcCommunicator("test-agent", {"test-service": "localhost:50051"})

        # Define a handler
        async def handler(param1):
            return {"result": "success", "param1": param1}

        # Register the handler
        await communicator.register_handler("test_method", handler)

        # Check that the handler was registered
        assert "test_method" in communicator.handlers
        assert communicator.handlers["test_method"] == handler

    @pytest.mark.asyncio
    async def test_start_server_mode(self):
        """Test starting the communicator in server mode."""
        # Create a real server mock that returns a simple MagicMock (not AsyncMock)
        mock_server_instance = mock.MagicMock()
        mock_server_instance.add_insecure_port.return_value = 50053  # Just return a port number
        mock_server_instance.start = mock.AsyncMock()  # This will be awaited

        # Create a server factory function that returns our instance
        def mock_server_factory(*args, **kwargs):
            return mock_server_instance

        mock_servicer = mock.MagicMock()
        mock_servicer_class = mock.MagicMock(return_value=mock_servicer)

        mock_add_servicer = mock.MagicMock()

        # Apply the patches
        with mock.patch("simple_mas.communication.grpc.communicator.aio_server", mock_server_factory), mock.patch(
            "simple_mas.communication.grpc.communicator.SimpleMasServicer", mock_servicer_class
        ), mock.patch(
            "simple_mas.communication.grpc.communicator.add_SimpleMasServiceServicer_to_server", mock_add_servicer
        ):
            # Create and start the communicator
            communicator = GrpcCommunicator("test-agent", {}, server_mode=True, server_address="[::]:50053")
            await communicator.start()

            # Check that the server was created and stored
            assert communicator.server is mock_server_instance
            assert communicator.servicer is mock_servicer

            # Verify server methods were called correctly
            mock_server_instance.add_insecure_port.assert_called_once_with("[::]:50053")
            mock_server_instance.start.assert_awaited_once()
            mock_add_servicer.assert_called_once_with(mock_servicer, mock_server_instance)

    @pytest.mark.asyncio
    async def test_start_client_mode(self):
        """Test starting the communicator in client mode."""
        communicator = GrpcCommunicator("test-agent", {"test-service": "localhost:50051"})

        # Start the communicator
        await communicator.start()

        # In client mode, no server should be created
        assert communicator.server is None

    @pytest.mark.asyncio
    async def test_stop_server_mode(self):
        """Test stopping the communicator in server mode."""
        # Create an async mock for the server
        mock_server = mock.AsyncMock()
        mock_server.stop = mock.AsyncMock()

        # Create a communicator and set its server to our mock
        communicator = GrpcCommunicator("test-agent", {}, server_mode=True)
        communicator.server = mock_server

        # Stop the communicator
        await communicator.stop()

        # Check that the server was stopped
        mock_server.stop.assert_awaited_once_with(grace=1.0)

    @pytest.mark.asyncio
    async def test_stop_client_mode(self):
        """Test stopping the communicator in client mode."""
        communicator = GrpcCommunicator("test-agent", {"test-service": "localhost:50051"})

        # Mock the channels
        mock_channel1 = mock.AsyncMock()
        mock_channel2 = mock.AsyncMock()
        communicator._channels = {"test-service": mock_channel1, "other-service": mock_channel2}

        # Stop the communicator
        await communicator.stop()

        # Check that all channels were closed
        mock_channel1.close.assert_called_once()
        mock_channel2.close.assert_called_once()


class TestSimpleMasServicer:
    """Tests for the SimpleMasServicer class."""

    @pytest.mark.asyncio
    async def test_send_request_success(self, test_servicer):
        """Test the servicer's SendRequest method."""
        servicer, communicator = test_servicer

        # Mock a handler
        async def handler(param1):
            return {"result": "success", "param1": param1}

        communicator.handlers = {"test_method": handler}

        # Create a request
        request = pb2.RequestMessage(
            id=str(uuid.uuid4()),
            source="test-agent",
            target="test-service",
            method="test_method",
            params=json.dumps({"param1": "value1"}),
            timestamp=int(time.time() * 1000),
        )

        # Mock the context
        context = mock.AsyncMock()

        # Make the request
        response = await servicer.SendRequest(request, context)

        # Check the response
        assert response.id == request.id
        assert response.source == request.target
        assert response.target == request.source
        assert response.error.code == 0

        # Check the result
        result_json = json.loads(response.result.decode())
        assert result_json["result"] == "success"
        assert result_json["param1"] == "value1"

    @pytest.mark.asyncio
    async def test_send_request_method_not_found(self, test_servicer):
        """Test the servicer's SendRequest method with a non-existent method."""
        servicer, communicator = test_servicer

        communicator.handlers = {}

        # Create a request for a non-existent method
        request = pb2.RequestMessage(
            id=str(uuid.uuid4()),
            source="test-agent",
            target="test-service",
            method="non_existent_method",
            params="{}",
            timestamp=int(time.time() * 1000),
        )

        # Mock the context
        context = mock.AsyncMock()

        # Make the request
        response = await servicer.SendRequest(request, context)

        # Check the response
        assert response.id == request.id
        assert response.source == request.target
        assert response.target == request.source
        assert response.error.code == 404
        assert "Method 'non_existent_method' not found" in response.error.message
        assert response.error.details == "MethodNotFoundError"

    @pytest.mark.asyncio
    async def test_send_request_handler_error(self, test_servicer):
        """Test the servicer's SendRequest method with a handler that raises an exception."""
        servicer, communicator = test_servicer

        # Mock a handler that raises an exception
        async def handler(param1):
            raise ValueError("Test error")

        communicator.handlers = {"test_method": handler}

        # Create a request
        request = pb2.RequestMessage(
            id=str(uuid.uuid4()),
            source="test-agent",
            target="test-service",
            method="test_method",
            params=json.dumps({"param1": "value1"}),
            timestamp=int(time.time() * 1000),
        )

        # Mock the context
        context = mock.AsyncMock()

        # Make the request
        response = await servicer.SendRequest(request, context)

        # Check the response
        assert response.id == request.id
        assert response.source == request.target
        assert response.target == request.source
        assert response.error.code == 500
        assert "Test error" in response.error.message
        assert response.error.details == "ValueError"

    @pytest.mark.asyncio
    async def test_send_notification(self, test_servicer):
        """Test the servicer's SendNotification method."""
        servicer, communicator = test_servicer

        # Mock a handler
        handler = mock.AsyncMock()

        communicator.handlers = {"test_method": handler}

        # Create a notification
        notification = pb2.NotificationMessage(
            source="test-agent",
            target="test-service",
            method="test_method",
            params=json.dumps({"param1": "value1"}),
            timestamp=int(time.time() * 1000),
        )

        # Mock the context
        context = mock.AsyncMock()

        # Send the notification
        response = await servicer.SendNotification(notification, context)

        # Check the response
        assert isinstance(response, pb2.Empty)

        # Check that create_task was called with the handler
        await asyncio.sleep(0.1)  # Wait for any async tasks to complete
        communicator.handlers["test_method"].assert_called_once_with(param1="value1")

    @pytest.mark.asyncio
    async def test_send_notification_method_not_found(self, test_servicer):
        """Test the servicer's SendNotification method with a non-existent method."""
        servicer, communicator = test_servicer

        communicator.handlers = {}

        # Create a notification for a non-existent method
        notification = pb2.NotificationMessage(
            source="test-agent",
            target="test-service",
            method="non_existent_method",
            params="{}",
            timestamp=int(time.time() * 1000),
        )

        # Mock the context
        context = mock.AsyncMock()

        # Send the notification
        response = await servicer.SendNotification(notification, context)

        # Even for non-existent methods, an Empty response should be returned
        assert isinstance(response, pb2.Empty)
