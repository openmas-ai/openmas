"""Fixtures for HTTP communicator tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def event_loop():
    """Fixture to create a new event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def communicator_config():
    """Fixture to provide standard communicator configuration."""
    return {
        "agent_name": "test-agent",
        "service_urls": {
            "test-service": "http://localhost:9000",
            "another-service": "http://localhost:9001",
        },
    }


@pytest.fixture
def mock_httpx():
    """Fixture to mock the HTTPX client."""
    # Create a mock client
    mock_client = MagicMock()

    # Mock the client's post and aclose methods
    mock_client.post = AsyncMock()
    mock_client.aclose = AsyncMock()

    # Create a mock constructor that returns our client
    mock_constructor = MagicMock(return_value=mock_client)

    # Patch the Client constructor
    with patch("openmas.communication.http.httpx.AsyncClient", mock_constructor):
        yield mock_constructor, mock_client
