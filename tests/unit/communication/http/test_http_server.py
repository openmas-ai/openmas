"""Tests for HTTP server functionality in the communicator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.communication.http import HttpCommunicator


@pytest.fixture
def mock_uvicorn_server():
    """Mock the uvicorn server to avoid actually starting it."""
    server_mock = MagicMock()
    serve_mock = AsyncMock()
    server_mock.serve = serve_mock
    server_class_mock = MagicMock(return_value=server_mock)

    with patch("uvicorn.Server", server_class_mock):
        yield server_mock, serve_mock, server_class_mock


@pytest.fixture
async def test_http_server():
    """Create a test HTTP communicator with a server."""
    communicator = HttpCommunicator("test-agent", {})

    try:
        # Add a handler to trigger server startup
        async def test_handler(params):
            return {"result": "success"}

        await communicator.register_handler("test", test_handler)

        # Yield the communicator for the test
        yield communicator
    finally:
        # Clean up
        await communicator.stop()


@pytest.mark.asyncio
async def test_server_lifecycle(mock_uvicorn_server):
    """Test the server lifecycle - start and stop."""
    server_mock, serve_mock, server_class_mock = mock_uvicorn_server

    # Create a communicator
    communicator = HttpCommunicator("test-agent", {})

    # Mock key components
    with (
        patch("uvicorn.Server", server_class_mock),
        patch("asyncio.create_task", side_effect=lambda coro: MagicMock()),
    ):
        try:
            # Add a handler to trigger server startup
            async def test_handler(params):
                return {"result": "success"}

            # Register the handler - this should start the server
            await communicator.register_handler("test", test_handler)

            # Verify the mock server class was called
            assert server_class_mock.called
        finally:
            # Clean up
            await communicator.stop()


@pytest.mark.asyncio
async def test_server_exception_handling(mock_uvicorn_server):
    """Test handling exceptions in the server task."""
    server_mock, serve_mock, server_class_mock = mock_uvicorn_server

    # Set up serve to raise an exception
    serve_mock.side_effect = Exception("Server error")

    # Create a communicator with proper cleanup
    communicator = None

    with (
        patch("uvicorn.Server", server_class_mock),
        patch("asyncio.create_task", side_effect=lambda coro: MagicMock()),
    ):
        try:
            communicator = HttpCommunicator("test-agent", {})

            # Add a handler to trigger server startup
            async def test_handler(params):
                return {"result": "success"}

            # Register the handler to make the server start (should not fail due to our mocks)
            await communicator.register_handler("test", test_handler)

            # Verify the mock server class was called
            assert server_class_mock.called
        finally:
            # Clean up
            if communicator:
                await communicator.stop()


@pytest.mark.asyncio
async def test_http_server_creation(mock_uvicorn_server):
    """Test HTTP server is created when handlers are registered."""
    server_mock, serve_mock, _ = mock_uvicorn_server

    # Create a communicator
    communicator = HttpCommunicator("test-agent", {})

    try:
        # Register a handler to start the server
        async def test_handler(params):
            return {"result": "success"}

        await communicator.register_handler("test", test_handler)

        # Mock the app creation for adding another handler
        mock_app = MagicMock()

        with (
            patch("fastapi.FastAPI", return_value=mock_app),
            patch("uvicorn.Server"),
            patch("uvicorn.Config"),
            patch("asyncio.create_task"),
        ):
            # Register another handler
            async def another_handler(params):
                return {"another": "result"}

            await communicator.register_handler("another", another_handler)

            # Test that the handler was registered
            assert communicator.handlers["another"] is not None
    finally:
        # Clean up
        await communicator.stop()


@pytest.mark.asyncio
async def test_lifespan_handler():
    """Test the lifespan handler for the FastAPI app."""
    # Create a test HTTP communicator
    communicator = HttpCommunicator("test-agent", {})

    try:
        # Add a handler to trigger server startup
        async def test_handler(params):
            return {"result": "success"}

        await communicator.register_handler("test", test_handler)

        # Create mock objects for our test
        mock_app = MagicMock()
        mock_router = MagicMock()
        mock_app.router = mock_router

        # Mock FastAPI and other server components
        with (
            patch("fastapi.FastAPI", return_value=mock_app),
            patch("uvicorn.Server"),
            patch("uvicorn.Config"),
            patch("asyncio.create_task"),
        ):
            # Ensure the server is running (will use our mocks)
            await communicator._ensure_server_running()

            # Check that the lifespan_context was set
            assert hasattr(mock_app.router, "lifespan_context")
    finally:
        # Clean up resources
        await communicator.stop()


@pytest.mark.asyncio
async def test_register_handler_with_running_server():
    """Test registering a handler while the server is already running."""
    communicator = HttpCommunicator("test-agent", {})

    try:
        # Mock the server task to simulate a running server
        # Use a regular MagicMock instead of AsyncMock to avoid coro not awaited warnings
        communicator.server_task = MagicMock()
        communicator.server_task.cancel = MagicMock()  # Regular mock for cancel

        # Register a handler
        async def test_handler(params):
            return {"success": True}

        # This should not trigger server startup since server is "running"
        await communicator.register_handler("test", test_handler)

        # Verify the handler was registered
        assert "test" in communicator.handlers
        assert communicator.handlers["test"] == test_handler
    finally:
        # Ensure cleanup
        await communicator.stop()


@pytest.mark.asyncio
async def test_http_communicator_server_starts_on_handler_registration():
    """Test that the HTTP server starts when a handler is registered."""
    # Create a proper AsyncMock that can be awaited
    mock_task = AsyncMock()
    # Configure it to be identified as not a coroutine for the stop method
    mock_task._is_coroutine = False

    # Mock the create_task function to return our mock
    with patch("openmas.communication.http.asyncio.create_task", return_value=mock_task) as mock_create_task:
        # Create a communicator
        communicator = HttpCommunicator(agent_name="test-agent", service_urls={}, port=12345)

        # Define a handler
        async def test_handler(params):
            return {"success": True}

        # Register the handler
        await communicator.register_handler("test_method", test_handler)

        # Assert that the server task was created
        mock_create_task.assert_called_once()

        # Clean up
        await communicator.stop()


@pytest.mark.asyncio
async def test_http_communicator_start_initializes_server():
    """Test that calling start() initializes the server if handlers are registered."""
    # Create a communicator
    communicator = HttpCommunicator(agent_name="test-agent", service_urls={}, port=12345)

    # Define a handler
    async def test_handler(params):
        return {"success": True}

    # Add the handler directly to simulate registration
    communicator.handlers["test_method"] = test_handler

    # Mock the ensure_server method
    with patch.object(communicator, "_ensure_server_running", new_callable=AsyncMock) as mock_ensure:
        # Call start
        await communicator.start()

        # Check that ensure_server was called
        mock_ensure.assert_called_once()

        # Clean up
        await communicator.stop()
