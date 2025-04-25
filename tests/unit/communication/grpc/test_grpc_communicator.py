"""Tests for the gRPC communicator."""

import asyncio
import json
import time
import uuid
from unittest import mock

import pytest
from pydantic import BaseModel

# Conditional import for grpc - this way we can at least run other tests if grpc not installed
try:
    import grpc

    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False

    # Create a mock grpc module with the necessary components for testing
    class MockGrpcModule:
        """A mock implementation of gRPC module for testing without gRPC dependencies.

        This class provides minimal gRPC functionality needed for tests to run
        even when the actual gRPC library is not installed.
        """

        class StatusCode:
            """Mock implementation of gRPC StatusCode enum."""

            OK = 0
            CANCELLED = 1
            UNKNOWN = 2
            INVALID_ARGUMENT = 3
            DEADLINE_EXCEEDED = 4
            NOT_FOUND = 5
            ALREADY_EXISTS = 6
            PERMISSION_DENIED = 7
            UNAUTHENTICATED = 16
            RESOURCE_EXHAUSTED = 8
            FAILED_PRECONDITION = 9
            ABORTED = 10
            OUT_OF_RANGE = 11
            UNIMPLEMENTED = 12
            INTERNAL = 13
            UNAVAILABLE = 14
            DATA_LOSS = 15

    grpc = MockGrpcModule()

# Import exceptions - these don't depend on gRPC being available
from openmas.exceptions import CommunicationError, MethodNotFoundError, RequestTimeoutError, ServiceNotFoundError

# Don't try to load components at module level - defer to each test
# We'll mark the tests with pytest.mark.skipif to skip if gRPC not available


# Create a custom mock RpcError for testing
class MockRpcError(Exception):
    """Mock RpcError for testing gRPC error handling.

    This class simulates gRPC RpcError exceptions with status codes
    for testing error handling in the gRPC communicator.
    """

    def __init__(self, details="Mock RPC Error", code=grpc.StatusCode.UNKNOWN):
        """Initialize the mock error with details and status code.

        Args:
            details: Error details message
            code: gRPC status code
        """
        self._code = code
        self._details = details
        super().__init__(details)

    def code(self):
        """Return the error status code.

        Returns:
            The gRPC status code
        """
        return self._code

    def details(self):
        """Return the error details.

        Returns:
            The error details string
        """
        return self._details


class ResponseModel(BaseModel):
    """A test response model."""

    result: str
    value: int


# Helper function to get gRPC components, used by tests when needed
def get_grpc_components():
    """Get gRPC communicator and proto components on demand."""
    from openmas.communication import _load_grpc_communicator

    GrpcCommunicator = _load_grpc_communicator()
    from openmas.communication.grpc import openmas_pb2 as pb2
    from openmas.communication.grpc.communicator import OpenMasServicer

    return GrpcCommunicator, pb2, OpenMasServicer


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
    # Skip if gRPC not available
    if not HAS_GRPC:
        pytest.skip("gRPC not available")

    # Get proto messages dynamically
    _, pb2, _ = get_grpc_components()

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
    """Create a OpenMasServicer for testing."""
    # Skip if gRPC not available
    if not HAS_GRPC:
        pytest.skip("gRPC not available")

    GrpcCommunicator, _, OpenMasServicer = get_grpc_components()

    communicator = mock.AsyncMock(spec=GrpcCommunicator)
    communicator.agent_name = "test-agent"
    communicator.handlers = {}
    servicer = OpenMasServicer(communicator)
    return servicer, communicator


# Mark all tests to be skipped if grpc is not available
pytestmark = pytest.mark.skipif(
    not HAS_GRPC,
    reason="Tests will be skipped if gRPC dependencies are not available",
)


class TestGrpcCommunicator:
    """Tests for the GrpcCommunicator class."""

    def test_initialization(self):
        """Test that initialization sets up the communicator correctly."""
        GrpcCommunicator, _, _ = get_grpc_components()

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
        GrpcCommunicator, _, _ = get_grpc_components()

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
        GrpcCommunicator, pb2, _ = get_grpc_components()

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

        # Check the result is a ResponseModel instance
        assert isinstance(result, ResponseModel)
        assert result.result == "success"
        assert result.value == 42

    @pytest.mark.asyncio
    async def test_send_request_service_not_found(self):
        """Test sending a request to a non-existent service."""
        GrpcCommunicator, _, _ = get_grpc_components()

        # Create a communicator with no service URLs
        communicator = GrpcCommunicator("test-agent", {})

        # Try to send a request to a non-existent service
        with pytest.raises(ServiceNotFoundError):
            await communicator.send_request("non-existent-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_method_not_found(self, mock_grpc_channel):
        """Test sending a request for a non-existent method."""
        GrpcCommunicator, pb2, _ = get_grpc_components()

        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Create a mock response with an error for method not found
        mock_response = mock.MagicMock()
        mock_response.error.code = 404
        mock_response.error.message = "Method not found"
        mock_response.error.details = "MethodNotFoundError"
        mock_response.result = b""

        # Mock the stub
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(return_value=mock_response)

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Try to send a request for a non-existent method
        with pytest.raises(MethodNotFoundError):
            await communicator.send_request("test-service", "non_existent_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_request_error(self, mock_grpc_channel):
        """Test sending a request that results in an error."""
        GrpcCommunicator, _, _ = get_grpc_components()

        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Create a mock response with an error
        mock_response = mock.MagicMock()
        mock_response.error.code = 1
        mock_response.error.message = "Test error"
        mock_response.error.details = "Error details"
        mock_response.result = b""

        # Mock the stub
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(return_value=mock_response)

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Try to send a request
        with pytest.raises(CommunicationError) as excinfo:
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

        # Check the error
        assert "Test error" in str(excinfo.value)
        assert "test-service" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_send_request_grpc_error(self, mock_grpc_channel):
        """Test sending a request that results in a gRPC error."""
        GrpcCommunicator, _, _ = get_grpc_components()

        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Create a gRPC error
        error = MockRpcError("Test gRPC error", grpc.StatusCode.INTERNAL)

        # Mock the stub with an error
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(side_effect=error)

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Try to send a request
        with pytest.raises(CommunicationError) as excinfo:
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

        # Check the error
        assert "Test gRPC error" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_send_request_timeout(self, mock_grpc_channel):
        """Test sending a request that times out due to gRPC DEADLINE_EXCEEDED."""
        GrpcCommunicator, _, _ = get_grpc_components()

        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Create a gRPC error for timeout
        error = MockRpcError("Deadline exceeded", grpc.StatusCode.DEADLINE_EXCEEDED)

        # Mock the stub with a timeout error
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(side_effect=error)

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Try to send a request
        with pytest.raises(RequestTimeoutError) as excinfo:
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

        # Check the error
        assert "Request to '" in str(excinfo.value)
        assert "test-service" in str(excinfo.value)
        assert "timed out" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_send_request_asyncio_timeout(self, mock_grpc_channel):
        """Test sending a request that times out due to asyncio.TimeoutError."""
        GrpcCommunicator, _, _ = get_grpc_components()

        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Instead of mocking _get_stub with a TimeoutError, use a mock stub
        # and have SendRequest raise the TimeoutError
        mock_stub = mock.AsyncMock()
        mock_stub.SendRequest = mock.AsyncMock(side_effect=asyncio.TimeoutError("Asyncio timeout"))

        # Mock the stub getter to return our mock
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Try to send a request
        with pytest.raises(RequestTimeoutError) as excinfo:
            await communicator.send_request("test-service", "test_method", {"param1": "value1"})

        # Check the error
        assert "Request to '" in str(excinfo.value)
        assert "test-service" in str(excinfo.value)
        assert "timed out" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_error_mapping(self, mock_grpc_channel):
        """Test mapping of gRPC status codes to OpenMasError types."""
        GrpcCommunicator, _, _ = get_grpc_components()

        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Test various error mappings
        error_map = {
            grpc.StatusCode.DEADLINE_EXCEEDED: RequestTimeoutError,
            grpc.StatusCode.UNAVAILABLE: ServiceNotFoundError,
            grpc.StatusCode.INVALID_ARGUMENT: CommunicationError,
            grpc.StatusCode.INTERNAL: CommunicationError,
        }

        # Add test for UNIMPLEMENTED separately
        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock()

        for code, error_type in error_map.items():
            # Create a gRPC error
            error = MockRpcError(f"Error with code {code}", code)

            # Mock the stub
            mock_stub = mock.AsyncMock()
            mock_stub.SendRequest = mock.AsyncMock(side_effect=error)
            communicator._get_stub.return_value = mock_stub

            # Try to send a request
            with pytest.raises(error_type):
                await communicator.send_request("test-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_grpc_channel, mock_grpc_stub):
        """Test sending a notification successfully."""
        GrpcCommunicator, _, _ = get_grpc_components()

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
        GrpcCommunicator, _, _ = get_grpc_components()

        # Create a communicator with no service URLs
        communicator = GrpcCommunicator("test-agent", {})

        # Try to send a notification to a non-existent service
        with pytest.raises(ServiceNotFoundError):
            await communicator.send_notification("non-existent-service", "test_method", {"param1": "value1"})

    @pytest.mark.asyncio
    async def test_send_notification_error(self, mock_grpc_channel):
        """Test sending a notification that results in an error."""
        GrpcCommunicator, _, _ = get_grpc_components()

        service_urls = {"test-service": "localhost:50051"}
        communicator = GrpcCommunicator("test-agent", service_urls)

        # Create a gRPC error
        error = MockRpcError("Test gRPC error", grpc.StatusCode.INTERNAL)

        # Mock the stub with an error
        mock_stub = mock.AsyncMock()
        mock_stub.SendNotification = mock.AsyncMock(side_effect=error)

        # Mock the stub getter
        communicator._get_stub = mock.AsyncMock(return_value=mock_stub)

        # Try to send a notification
        with pytest.raises(CommunicationError) as excinfo:
            await communicator.send_notification("test-service", "test_method", {"param1": "value1"})

        # Check the error
        assert "Test gRPC error" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_register_handler(self):
        """Test registering a handler."""
        GrpcCommunicator, _, _ = get_grpc_components()

        communicator = GrpcCommunicator("test-agent", {"test-service": "localhost:50051"})

        # Define a handler
        async def handler(param1):
            return {"result": param1}

        # Register the handler
        await communicator.register_handler("test_method", handler)

        # Check that the handler was registered
        assert "test_method" in communicator.handlers
        assert communicator.handlers["test_method"] == handler

    @pytest.mark.asyncio
    async def test_start_server_mode(self):
        """Test starting the communicator in server mode."""
        GrpcCommunicator, _, _ = get_grpc_components()

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
        with mock.patch("openmas.communication.grpc.communicator.aio_server", mock_server_factory), mock.patch(
            "openmas.communication.grpc.communicator.OpenMasServicer", mock_servicer_class
        ), mock.patch(
            "openmas.communication.grpc.communicator.add_OpenMasServiceServicer_to_server", mock_add_servicer
        ):
            # Create and start the communicator
            communicator = GrpcCommunicator("test-agent", {}, server_mode=True, server_address="[::]:50053")
            await communicator.start()

            # Check that the server was created and started
            assert communicator.server is not None
            assert communicator.servicer is not None
            mock_server_instance.add_insecure_port.assert_called_once_with("[::]:50053")
            mock_server_instance.start.assert_called_once()
            mock_add_servicer.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_client_mode(self):
        """Test starting the communicator in client mode."""
        GrpcCommunicator, _, _ = get_grpc_components()

        communicator = GrpcCommunicator("test-agent", {"test-service": "localhost:50051"})
        await communicator.start()

        # In client mode, start() doesn't do much, so just verify it doesn't fail
        assert communicator.server is None

    @pytest.mark.asyncio
    async def test_stop_server_mode(self):
        """Test stopping the communicator in server mode."""
        GrpcCommunicator, _, _ = get_grpc_components()

        # Create an async mock for the server
        mock_server = mock.AsyncMock()
        mock_server.stop = mock.AsyncMock()

        # Create a communicator and set its server to our mock
        communicator = GrpcCommunicator("test-agent", {}, server_mode=True)
        communicator.server = mock_server

        # Stop the communicator
        await communicator.stop()

        # Check that the server was stopped
        mock_server.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_client_mode(self):
        """Test stopping the communicator in client mode."""
        GrpcCommunicator, _, _ = get_grpc_components()

        communicator = GrpcCommunicator("test-agent", {"test-service": "localhost:50051"})
        await communicator.stop()

        # In client mode, stop() doesn't do much, so just verify it doesn't fail
        assert communicator.server is None


class TestOpenMasServicer:
    """Tests for the OpenMasServicer class."""

    @pytest.mark.asyncio
    async def test_send_request_success(self, test_servicer):
        """Test the servicer's SendRequest method."""
        servicer, communicator = test_servicer
        GrpcCommunicator, pb2, _ = get_grpc_components()

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

        # Call the method
        response = await servicer.SendRequest(request, None)

        # Check the response
        assert response.id == request.id
        assert response.source == request.target
        assert response.target == request.source
        assert response.error.code == 0
        assert response.error.message == ""

        # Parse the result
        result = json.loads(response.result)
        assert result["result"] == "success"
        assert result["param1"] == "value1"

    @pytest.mark.asyncio
    async def test_send_request_method_not_found(self, test_servicer):
        """Test the servicer's SendRequest method with a non-existent method."""
        servicer, communicator = test_servicer
        GrpcCommunicator, pb2, _ = get_grpc_components()

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

        # Call the method
        response = await servicer.SendRequest(request, None)

        # Check the response has an error
        assert response.error.code == 404
        assert "not found" in response.error.message
        assert "MethodNotFoundError" in response.error.details

    @pytest.mark.asyncio
    async def test_send_request_handler_error(self, test_servicer):
        """Test the servicer's SendRequest method with a handler that raises an exception."""
        servicer, communicator = test_servicer
        GrpcCommunicator, pb2, _ = get_grpc_components()

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

        # Call the method
        response = await servicer.SendRequest(request, None)

        # Check the response has an error
        assert response.error.code == 500
        assert "Test error" in response.error.message
        assert "ValueError" in response.error.details

    @pytest.mark.asyncio
    async def test_send_notification(self, test_servicer):
        """Test the servicer's SendNotification method."""
        servicer, communicator = test_servicer
        GrpcCommunicator, pb2, _ = get_grpc_components()

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

        # Call the method
        response = await servicer.SendNotification(notification, None)

        # Check the response is an Empty
        assert isinstance(response, pb2.Empty)

        # Check the handler was called - note: using asyncio.create_task means we need
        # to wait a bit for the task to be scheduled
        await asyncio.sleep(0.1)
        handler.assert_called_once_with(param1="value1")

    @pytest.mark.asyncio
    async def test_send_notification_method_not_found(self, test_servicer):
        """Test the servicer's SendNotification method with a non-existent method."""
        servicer, communicator = test_servicer
        GrpcCommunicator, pb2, _ = get_grpc_components()

        communicator.handlers = {}

        # Create a notification for a non-existent method
        notification = pb2.NotificationMessage(
            source="test-agent",
            target="test-service",
            method="non_existent_method",
            params="{}",
            timestamp=int(time.time() * 1000),
        )

        # Call the method - should not raise an exception
        response = await servicer.SendNotification(notification, None)

        # Check the response is an Empty
        assert isinstance(response, pb2.Empty)

        # But the error should be logged (hard to test)
