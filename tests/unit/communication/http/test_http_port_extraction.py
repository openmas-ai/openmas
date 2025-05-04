"""Tests for HTTP communicator port extraction functionality."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.communication.http import HttpCommunicator


@pytest.mark.asyncio
async def test_port_extraction_from_url():
    """Test that the communicator can extract port from a service URL."""
    # Setup a communicator with the agent name in service_urls
    agent_name = "test-agent"
    service_urls = {
        agent_name: "http://localhost:8765",
        "other-service": "http://localhost:9000",
    }

    # In the _ensure_server_running method, we're going to test the port extraction logic
    # To do that, we need to mock the actual server creation but let the port extraction run
    with (
        patch("fastapi.FastAPI", return_value=MagicMock()),
        patch("uvicorn.Server", return_value=MagicMock()),
        patch("uvicorn.Config"),
        patch("asyncio.create_task"),
    ):
        # Create the communicator
        communicator = HttpCommunicator(agent_name, service_urls)
        assert communicator.port is None

        # Mock handlers to trigger server initialization
        communicator.handlers = {"test_method": AsyncMock()}

        # Call the method that should extract the port
        await communicator._ensure_server_running()

        # Port should now be extracted from the URL
        assert communicator.port == 8765


@pytest.mark.asyncio
async def test_port_fallback_for_consumer():
    """Test that the communicator uses the fallback port for 'consumer' agent."""
    # Setup with an agent name not in service_urls
    agent_name = "consumer"
    service_urls = {
        "other-service": "http://localhost:9000",
    }

    # In the _ensure_server_running method, we're going to test the port fallback logic
    with (
        patch("fastapi.FastAPI", return_value=MagicMock()),
        patch("uvicorn.Server", return_value=MagicMock()),
        patch("uvicorn.Config"),
        patch("asyncio.create_task"),
    ):
        # Create the communicator
        communicator = HttpCommunicator(agent_name, service_urls)
        assert communicator.port is None

        # Mock handlers to trigger server initialization
        communicator.handlers = {"test_method": AsyncMock()}

        # Call the method that should trigger the fallback port logic
        await communicator._ensure_server_running()

        # Port should now be the fallback for consumer
        assert communicator.port == 8082


@pytest.mark.asyncio
async def test_port_fallback_for_producer():
    """Test that the communicator uses the fallback port for 'producer' agent."""
    # Setup with an agent name not in service_urls
    agent_name = "producer"
    service_urls = {
        "other-service": "http://localhost:9000",
    }

    # In the _ensure_server_running method, we're going to test the port fallback logic
    with (
        patch("fastapi.FastAPI", return_value=MagicMock()),
        patch("uvicorn.Server", return_value=MagicMock()),
        patch("uvicorn.Config"),
        patch("asyncio.create_task"),
    ):
        # Create the communicator
        communicator = HttpCommunicator(agent_name, service_urls)
        assert communicator.port is None

        # Mock handlers to trigger server initialization
        communicator.handlers = {"test_method": AsyncMock()}

        # Call the method that should trigger the fallback port logic
        await communicator._ensure_server_running()

        # Port should now be the fallback for producer
        assert communicator.port == 8081


@pytest.mark.asyncio
async def test_port_fallback_for_other_agents():
    """Test that the communicator uses the default fallback port for other agents."""
    # Setup with an agent name not in service_urls
    agent_name = "some-other-agent"
    service_urls = {
        "other-service": "http://localhost:9000",
    }

    # In the _ensure_server_running method, we're going to test the port fallback logic
    with (
        patch("fastapi.FastAPI", return_value=MagicMock()),
        patch("uvicorn.Server", return_value=MagicMock()),
        patch("uvicorn.Config"),
        patch("asyncio.create_task"),
    ):
        # Create the communicator
        communicator = HttpCommunicator(agent_name, service_urls)
        assert communicator.port is None

        # Mock handlers to trigger server initialization
        communicator.handlers = {"test_method": AsyncMock()}

        # Call the method that should trigger the fallback port logic
        await communicator._ensure_server_running()

        # Port should now be the default fallback
        assert communicator.port == 8000
