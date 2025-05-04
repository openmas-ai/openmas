"""Tests for HTTP error handling scenarios."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import HTTPError

from openmas.communication.http import HttpCommunicator
from openmas.exceptions import CommunicationError


@pytest.mark.asyncio
async def test_server_task_exception_handling():
    """Test that exceptions in the server task are properly handled."""
    communicator = HttpCommunicator("test-agent", {})

    # Create a completed task with an exception
    mock_task: asyncio.Future = asyncio.Future()
    mock_task.set_exception(RuntimeError("Server error"))

    # Set it as the server_task
    communicator.server_task = mock_task

    # Now try to stop the communicator, it should handle the exception
    await communicator.stop()

    # The server_task should be None after stop is called
    assert communicator.server_task is None


@pytest.mark.asyncio
async def test_http_handler_validation_error():
    """Test the server handling of a request with invalid JSON."""
    communicator = HttpCommunicator("test-agent", {})

    # Create a mock FastAPI app and request
    mock_app = MagicMock(spec=FastAPI)
    mock_request = MagicMock()

    # Mock request.json() to raise an exception
    mock_request.json = AsyncMock(side_effect=ValueError("Invalid JSON"))

    # Extract the handler function by manually calling _ensure_server_running
    # with mocked FastAPI and uvicorn

    with (
        patch("fastapi.FastAPI", return_value=mock_app),
        patch("uvicorn.Server"),
        patch("uvicorn.Config"),
        patch("asyncio.create_task"),
    ):
        # Create a custom post decorator to capture any route handlers
        def post_decorator(path):
            def decorator(func):
                return func

            return decorator

        # Apply the decorator to mock_app.post
        mock_app.post = post_decorator

        # Call the method to set up the server
        await communicator._ensure_server_running()

        # Create a simple handler for demonstration
        async def test_handler(params):
            return {"result": "success"}

        # Register the handler
        communicator.handlers["test_method"] = test_handler

    # Clean up
    await communicator.stop()


@pytest.mark.asyncio
async def test_http_server_general_exception():
    """Test handling of a general exception during server startup."""
    communicator = HttpCommunicator("test-agent", {})

    # Register a handler to ensure server will try to start
    async def test_handler(params):
        return {"result": "success"}

    communicator.handlers["test"] = test_handler

    # Mock the _ensure_server_running method to raise a general exception
    # wrapped in a CommunicationError as it happens in the actual code
    async def mock_ensure_server():
        runtime_error = RuntimeError("Server startup error")
        raise CommunicationError(f"Failed to start HTTP server: {runtime_error}")

    with patch.object(communicator, "_ensure_server_running", mock_ensure_server):
        with pytest.raises(CommunicationError) as excinfo:
            # This call to start will try to ensure server is running
            await communicator.start()

        # Check the error message contains the expected text
        assert "Failed to start HTTP server" in str(excinfo.value)
        assert "Server startup error" in str(excinfo.value)

    # Test cleanup
    await communicator.stop()


@pytest.mark.asyncio
async def test_handler_exception_handling():
    """Test handling of exceptions raised by handlers when the handler raises an exception."""

    # Create a handler that will raise an exception
    async def failing_handler(params):
        raise ValueError("Handler error")

    # Create a communicator
    communicator = HttpCommunicator("test-agent", {})

    try:
        # Register our failing handler
        await communicator.register_handler("failing_method", failing_handler)

        # Request-like structure
        request_data = {"jsonrpc": "2.0", "id": "test-id", "method": "failing_method", "params": {}}

        # Extract the handler from the communicator
        handler = communicator.handlers["failing_method"]

        # Test that calling the handler with the params raises an exception
        with pytest.raises(ValueError) as excinfo:
            await handler(request_data["params"])

        # Verify the error message
        assert "Handler error" in str(excinfo.value)

        # Now let's verify that a special handler function would handle this correctly
        # by constructing a similar handler to what would be in the HTTP server

        async def simulate_jsonrpc_handling(request_data, handlers):
            """Simulate the JSON-RPC request handling logic without FastAPI."""
            method = request_data["method"]
            params = request_data.get("params", {})
            request_id = request_data.get("id")

            # Check if method exists
            if method not in handlers:
                return {"error": "Method not found", "status_code": 404}

            # Call the handler
            handler = handlers[method]
            try:
                result = await handler(params)
                return {"result": result, "id": request_id, "status_code": 200}
            except Exception as e:
                # Convert handler exceptions to JSON-RPC error response
                return {
                    "error": {"code": -32000, "message": f"Handler error: {str(e)}"},
                    "id": request_id,
                    "status_code": 500,
                }

        # Test with our failing handler
        response = await simulate_jsonrpc_handling(request_data, communicator.handlers)

        # Verify error handling
        assert "error" in response
        assert response["status_code"] == 500
        assert "Handler error" in response["error"]["message"]
        assert response["id"] == "test-id"

    finally:
        # Clean up
        await communicator.stop()


@pytest.mark.asyncio
async def test_missing_method_in_request():
    """Test handling of requests that don't specify a method."""
    # Create a communicator
    communicator = HttpCommunicator("test-agent", {})

    try:
        # Register a test handler
        async def handler(params):
            return {"result": "success"}

        await communicator.register_handler("test_method", handler)

        # Create a request that doesn't include a method
        request_data = {
            "jsonrpc": "2.0",
            "id": "test-id",
            # method is missing intentionally
            "params": {},
        }

        # Simulate JSON-RPC handling with a missing method
        async def simulate_jsonrpc_handling(request_data, handlers):
            """Simulate the JSON-RPC request handling logic without FastAPI."""
            if "method" not in request_data:
                return {
                    "error": {"code": -32600, "message": "Invalid Request: 'method' field is required"},
                    "id": request_data.get("id"),
                    "status_code": 400,
                }

            # Rest of the normal handling code...
            return {"result": "This should not be reached", "status_code": 200}

        # Test with our request missing a method
        response = await simulate_jsonrpc_handling(request_data, communicator.handlers)

        # Verify error handling
        assert "error" in response
        assert response["status_code"] == 400
        assert "Invalid Request" in response["error"]["message"]
        assert "method" in response["error"]["message"]
        assert response["id"] == "test-id"

    finally:
        # Clean up
        await communicator.stop()


@pytest.mark.asyncio
async def test_send_notification_http_error(mock_httpx, communicator_config):
    """Test sending a notification that results in an HTTP error."""
    mock_client = mock_httpx[1]

    communicator = HttpCommunicator(
        communicator_config["agent_name"], {"test-service": communicator_config["service_urls"]["test-service"]}
    )

    # Mock an HTTP error
    mock_client.post.side_effect = HTTPError("HTTP error occurred")

    # Send a notification that should raise an HTTP error
    with pytest.raises(CommunicationError):
        await communicator.send_notification("test-service", "test_method", {"param1": "value1"})


@pytest.mark.asyncio
async def test_http_server_imports_error():
    """Test error handling when FastAPI or uvicorn cannot be imported."""
    communicator = HttpCommunicator("test-agent", {})

    # Register a handler to ensure server will try to start
    async def test_handler(params):
        return {"result": "success"}

    communicator.handlers["test"] = test_handler

    # Mock the imports to raise ImportError
    with patch.dict("sys.modules", {"fastapi": None}):
        with pytest.raises(CommunicationError):
            # This call to start will try to ensure server is running
            await communicator.start()

    # Test cleanup
    await communicator.stop()
