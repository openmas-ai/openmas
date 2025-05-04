"""Tests for HTTP communicator error handling."""

from unittest.mock import AsyncMock, patch

import pytest

from openmas.communication.http import HttpCommunicator
from openmas.exceptions import CommunicationError


@pytest.mark.asyncio
async def test_server_startup_general_exception():
    """Test that the communicator handles general exceptions when starting the server."""
    # Create the communicator
    communicator = HttpCommunicator("test-agent", {"service": "http://localhost:8000"})

    # Mock handlers to trigger server initialization
    communicator.handlers = {"test_method": AsyncMock()}

    # Mock a general exception during server startup
    test_exception = Exception("Test server startup error")

    # Patch FastAPI creation to raise an exception
    with (
        patch("fastapi.FastAPI", side_effect=test_exception),
        patch("asyncio.create_task"),
        pytest.raises(CommunicationError) as exc_info,
    ):
        # Call the method directly to test the error handling
        await communicator._ensure_server_running()

    # Verify the exception was properly wrapped in a CommunicationError
    assert "Failed to start HTTP server" in str(exc_info.value)
    assert "Test server startup error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_server_startup_import_error():
    """Test that the communicator correctly handles ImportError during server startup."""
    # Create the communicator
    communicator = HttpCommunicator("test-agent", {"service": "http://localhost:8000"})

    # Set up handlers to trigger server initialization
    communicator.handlers = {"test_method": AsyncMock()}

    # We need to patch builtins.__import__ to control the import behavior
    original_import = __import__

    def mock_import(name, *args, **kwargs):
        if name == "uvicorn":
            raise ImportError("No module named 'uvicorn'")
        return original_import(name, *args, **kwargs)

    # Patch both __import__ and ensure server is never actually started
    with (
        patch("builtins.__import__", side_effect=mock_import),
        patch("asyncio.create_task"),
        pytest.raises(CommunicationError) as exc_info,
    ):
        # Call the method directly to test the error handling
        await communicator._ensure_server_running()

    # Verify the error message includes installation instructions
    assert "Cannot start HTTP server" in str(exc_info.value)
    assert "pip install fastapi uvicorn" in str(exc_info.value)
