"""Tests for HTTP communicator lifecycle (start, stop, etc.)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.communication.http import HttpCommunicator


@pytest.mark.asyncio
async def test_start_without_handlers():
    """Test starting the communicator without handlers."""
    communicator = HttpCommunicator("test-agent", {})

    try:
        # Start should not create a server if there are no handlers
        await communicator.start()

        # No server should have been started
        assert communicator.server_task is None
    finally:
        # Ensure cleanup
        await communicator.stop()


@pytest.mark.asyncio
async def test_lifecycle(mock_httpx):
    """Test the communicator lifecycle with start and stop methods."""
    mock_client = mock_httpx[1]
    communicator = HttpCommunicator("test-agent", {})

    # Start the communicator
    await communicator.start()

    # Check that the communicator is started
    # The HttpCommunicator doesn't actually set a flag, but we can verify the server_task is still None
    # as that's the expected behavior for the base HttpCommunicator (no server by default)
    assert communicator.server_task is None

    # Stop the communicator
    await communicator.stop()

    # Check that the communicator is stopped and client.aclose was called
    mock_client.aclose.assert_called_once()
    assert communicator.server_task is None


@pytest.mark.asyncio
async def test_stop_with_server_task():
    """Test stopping the communicator with an active server task."""
    communicator = HttpCommunicator("test-agent", {})

    # Create a mock task
    mock_task = MagicMock()
    mock_task.cancel = MagicMock()
    mock_task._is_coroutine = False  # Mark as a mock for special handling

    # Set it as the server task
    communicator.server_task = mock_task

    # Stop the communicator
    await communicator.stop()

    # Verify the task was cancelled
    mock_task.cancel.assert_called_once()
    assert communicator.server_task is None


@pytest.mark.asyncio
async def test_stop_with_real_server_task():
    """Test stopping the communicator with a real server task."""
    communicator = HttpCommunicator("test-agent", {})

    # Create a real coroutine function to be awaited
    async def mock_server():
        try:
            # This will keep running until cancelled
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            # Handle cancellation gracefully
            pass

    # Create a real task
    server_task = asyncio.create_task(mock_server())

    # Set it as the server task
    communicator.server_task = server_task

    # Wait a tiny bit to make sure the task is running
    await asyncio.sleep(0.1)

    # Stop the communicator
    await communicator.stop()

    # Verify the task was cancelled
    assert server_task.cancelled() or server_task.done()
    assert communicator.server_task is None


@pytest.mark.asyncio
async def test_stop_with_exception_during_cancel():
    """Test stopping the communicator when the server task raises an exception during cancellation."""
    communicator = HttpCommunicator("test-agent", {})

    # Create a mock task that raises an exception when cancelled
    mock_task = MagicMock()

    def cancel_with_exception():
        """Mock cancel that raises an exception."""
        raise RuntimeError("Failed to cancel")

    mock_task.cancel = cancel_with_exception
    mock_task._is_coroutine = False  # Mark as a mock for special handling

    # Set it as the server task
    communicator.server_task = mock_task

    # Stop the communicator - should handle the exception
    await communicator.stop()

    # The server_task should be None even though an exception was raised
    assert communicator.server_task is None


@pytest.mark.asyncio
async def test_stop_task_timeout_handling():
    """Test handling a task that doesn't respond to cancellation."""
    communicator = HttpCommunicator("test-agent", {})

    # Create a real coroutine function that ignores cancellation
    async def hanging_task():
        try:
            # This will keep running even if cancelled
            while True:
                try:
                    await asyncio.sleep(10)  # Long sleep
                except asyncio.CancelledError:
                    # Ignore cancellation to simulate a hanging task
                    continue
        except Exception:
            # Handle other exceptions
            pass

    # Create and set the task
    communicator.server_task = asyncio.create_task(hanging_task())

    # Mock asyncio.wait_for to simulate a timeout
    async def mock_wait_for(coro, timeout):
        """Mock wait_for that raises TimeoutError."""
        raise asyncio.TimeoutError("Task cancellation timed out")

    # Stop the communicator with a mocked wait_for
    with patch("asyncio.wait_for", mock_wait_for):
        await communicator.stop()

    # The server_task should be None even though it "timed out"
    assert communicator.server_task is None


@pytest.mark.asyncio
async def test_register_handler_with_server_already_running():
    """Test registering a handler when the server is already running."""
    communicator = HttpCommunicator("test-agent", {})

    try:
        # Register one handler
        async def handler1(params):
            return {"result": "success1"}

        await communicator.register_handler("test1", handler1)

        # Now the server should be started

        # Patch _ensure_server_running to verify it's not called again
        with patch.object(communicator, "_ensure_server_running", new_callable=AsyncMock) as mock_ensure:
            # Register another handler
            async def handler2(params):
                return {"result": "success2"}

            await communicator.register_handler("test2", handler2)

            # Verify handler was added without restarting server
            assert communicator.handlers["test2"] == handler2
            # Server should not be restarted
            mock_ensure.assert_not_called()
    finally:
        # Clean up
        await communicator.stop()
