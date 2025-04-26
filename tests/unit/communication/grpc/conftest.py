"""Fixtures for gRPC communication unit tests."""

import sys
from unittest import mock

import pytest


@pytest.fixture
def mock_grpc_environment():
    """Set up a mocked gRPC environment.

    This fixture creates mock objects for grpc, grpc.aio, and related
    components needed for testing gRPC communication.

    Returns:
        dict: A dictionary containing the mock objects
    """
    # Create mock grpc modules
    mock_grpc = mock.MagicMock()
    mock_grpc_aio = mock.MagicMock()

    # Set up mock server
    mock_server = mock.AsyncMock()
    mock_grpc_aio.server.return_value = mock_server

    # Add server methods
    mock_server.start = mock.AsyncMock()
    mock_server.stop = mock.AsyncMock()
    mock_server.add_insecure_port = mock.MagicMock(return_value=50051)
    mock_server.add_secure_port = mock.MagicMock(return_value=50052)

    # Set up mock channel
    mock_channel = mock.AsyncMock()
    mock_grpc_aio.insecure_channel.return_value = mock_channel
    mock_grpc_aio.secure_channel.return_value = mock_channel

    # Set up mock credentials
    mock_ssl_creds = mock.MagicMock()
    mock_grpc.ssl_channel_credentials.return_value = mock_ssl_creds

    # Create client stub
    mock_stub = mock.AsyncMock()

    # Link the modules
    mock_grpc.aio = mock_grpc_aio

    # Apply patches
    patches = [
        mock.patch.dict(sys.modules, {"grpc": mock_grpc}),
        mock.patch.dict(sys.modules, {"grpc.aio": mock_grpc_aio}),
    ]

    for patch in patches:
        patch.start()

    # Create the environment dictionary
    env = {
        "mock_grpc": mock_grpc,
        "mock_grpc_aio": mock_grpc_aio,
        "mock_server": mock_server,
        "mock_channel": mock_channel,
        "mock_stub": mock_stub,
        "patches": patches,
    }

    yield env

    # Stop all patches
    for patch in patches:
        patch.stop()


@pytest.fixture
def mock_grpc_servicer():
    """Create a mock gRPC servicer for testing.

    This fixture creates a mock object that can be used as a gRPC servicer
    implementation with predefined responses.

    Returns:
        MagicMock: A mock object with common servicer methods
    """
    mock_servicer = mock.AsyncMock()

    # Add default responses for common methods
    async def handle_request(request, context):
        """Mock implementation for handling requests."""
        return mock.MagicMock(result="success")

    mock_servicer.HandleRequest = handle_request

    return mock_servicer


@pytest.fixture
def mock_grpc_tools():
    """Mock the grpc_tools module for code generation tests.

    Returns:
        MagicMock: A mock for the grpc_tools module
    """
    mock_tools = mock.MagicMock()
    mock_protoc = mock.MagicMock()
    mock_tools.protoc = mock_protoc

    # Set up the main function to return success
    mock_protoc.main.return_value = 0

    # Apply the patch
    with mock.patch.dict(sys.modules, {"grpc_tools": mock_tools}):
        yield mock_tools
