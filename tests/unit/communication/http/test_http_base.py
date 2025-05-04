"""Tests for basic HTTP communicator functionality."""

from typing import Any, Dict
from unittest.mock import MagicMock, patch

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


def test_initialization(communicator_config):
    """Test that initialization sets up the communicator correctly."""
    communicator = HttpCommunicator(communicator_config["agent_name"], communicator_config["service_urls"])

    assert communicator.agent_name == communicator_config["agent_name"]
    assert communicator.service_urls == communicator_config["service_urls"]
    assert communicator.handlers == {}
    assert communicator.server_task is None


@pytest.mark.asyncio
async def test_http_communicator_with_port_from_config():
    """Test that the port is correctly extracted from config options."""
    # Create a communicator with config options
    communicator = HttpCommunicator(agent_name="test-agent", service_urls={}, communicator_options={"port": 9876})

    # Verify the port was set correctly
    assert communicator.port == 9876
    await communicator.stop()


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


def test_url_building():
    """Test that URLs are correctly built from service names."""
    service_url = "http://localhost:8001"
    service_name = "service1"

    # Create communicator with predetermined service URLs
    communicator = HttpCommunicator("test-agent", {service_name: service_url})

    # Simply verify the URL is stored correctly in the communicator
    assert communicator.service_urls[service_name] == service_url


def test_custom_port_config():
    """Test setting a custom port in the config."""
    # Specify a custom port
    custom_port = 9876

    # Create a communicator with port in communicator_options
    communicator = HttpCommunicator("test-agent", {}, communicator_options={"port": custom_port})

    # Verify the port is correctly set
    assert communicator.port == custom_port


@pytest.mark.asyncio
async def test_service_url_extraction():
    """Test the extraction of service URLs from the service URL dictionary."""
    # Setup service URLs
    service_urls = {
        "test-service": "http://localhost:8000",
        "my-agent": "http://localhost:8001",
    }

    # Create a communicator
    communicator = HttpCommunicator("my-agent", service_urls)

    # Check that the service URLs were extracted correctly
    assert communicator.service_urls["test-service"] == "http://localhost:8000"
    assert communicator.service_urls["my-agent"] == "http://localhost:8001"

    # Clean up
    await communicator.stop()
