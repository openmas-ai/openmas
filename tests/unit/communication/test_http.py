"""Tests for the HTTP communicator implementation."""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.communication.http import HttpCommunicator


class MockAsyncTask(MagicMock):
    """A mock for async tasks that properly handles cancel() and await."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This makes the mock awaitable but doesn't register as a coroutine
        self.__await__ = lambda: (yield from [])
        # Add this attribute to help the stop method identify it's not a real coroutine
        self._is_coroutine = False

    def cancel(self):
        """Override cancel to return None instead of a coroutine."""
        return None


@pytest.mark.asyncio
async def test_http_communicator_server_starts_on_handler_registration():
    """Test that the HTTP server starts when a handler is registered."""
    # Create a mock task that works with async code
    mock_task = MockAsyncTask()

    # Mock the create_task function to return our mock
    with patch("openmas.communication.http.asyncio.create_task", return_value=mock_task) as mock_create_task:
        # Create a communicator
        communicator = HttpCommunicator(agent_name="test-agent", service_urls={}, port=12345)

        # Define a handler
        async def test_handler(params: Dict[str, Any]) -> Dict[str, Any]:
            return {"success": True}

        # Register the handler
        await communicator.register_handler("test_method", test_handler)

        # Assert that the server task was created
        mock_create_task.assert_called_once()

        # Clean up - the task should be awaitable without issues now
        await communicator.stop()


@pytest.mark.asyncio
async def test_http_communicator_start_initializes_server():
    """Test that calling start() initializes the server if handlers are registered."""
    # Create a communicator
    communicator = HttpCommunicator(agent_name="test-agent", service_urls={}, port=12345)

    # Define a handler
    async def test_handler(params: Dict[str, Any]) -> Dict[str, Any]:
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


@pytest.mark.asyncio
async def test_http_communicator_with_port_from_config():
    """Test that the port is correctly extracted from config options."""
    # Create a communicator with config options
    communicator = HttpCommunicator(agent_name="test-agent", service_urls={}, communicator_options={"port": 9876})

    # Verify the port was set correctly
    assert communicator.port == 9876


@pytest.mark.asyncio
async def test_http_communicator_uses_default_port_when_none_provided():
    """Test that a default port is used when none is provided."""
    # Create a mock task that works with async code
    mock_task = MockAsyncTask()

    # We need to capture the port when _ensure_server_running is called
    original_ensure_server = HttpCommunicator._ensure_server_running
    consumer_port = None
    producer_port = None

    async def mock_ensure_server(self):
        """Mock that captures the port and then calls the original."""
        nonlocal consumer_port, producer_port
        if self.agent_name == "consumer":
            # The port will be determined in the original method
            await original_ensure_server(self)
            consumer_port = self.port
        elif self.agent_name == "producer":
            # The port will be determined in the original method
            await original_ensure_server(self)
            producer_port = self.port

    # Mock create_task to return our proper mock and patch _ensure_server_running
    with (
        patch("openmas.communication.http.asyncio.create_task", return_value=mock_task),
        patch.object(HttpCommunicator, "_ensure_server_running", mock_ensure_server),
    ):
        # Create communicators for different agent types
        consumer = HttpCommunicator(agent_name="consumer", service_urls={})

        producer = HttpCommunicator(agent_name="producer", service_urls={})

        # Define a mock handler
        async def test_handler(params: Dict[str, Any]) -> Dict[str, Any]:
            return {"success": True}

        try:
            # Register handlers
            await consumer.register_handler("test_method", test_handler)
            await producer.register_handler("test_method", test_handler)

            # Verify the ports were set correctly (consumer=8082, producer=8081)
            assert consumer_port == 8082
            assert producer_port == 8081
        finally:
            # Clean up
            await consumer.stop()
            await producer.stop()
