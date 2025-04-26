"""Fixtures for communication unit tests."""

import json
from typing import Any, Awaitable, Callable, Dict
from unittest import mock

import pytest


@pytest.fixture
def mock_httpx():
    """Mock httpx module for HTTP-based communicators.

    Returns:
        tuple: (mock_httpx_module, mock_client)
    """
    # Create a mock response
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "success"}
    mock_response.text = json.dumps({"result": "success"})
    mock_response.content = json.dumps({"result": "success"}).encode("utf-8")

    # Create a mock client
    mock_client = mock.AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.post.return_value = mock_response
    mock_client.put.return_value = mock_response
    mock_client.delete.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    # Create a mock for the httpx module
    mock_httpx_module = mock.MagicMock()
    mock_httpx_module.AsyncClient.return_value = mock_client

    # Apply the patch
    with mock.patch("httpx.AsyncClient", return_value=mock_client):
        yield mock_httpx_module, mock_client


@pytest.fixture
def communicator_config():
    """Create a standard configuration for communicator tests."""
    return {
        "agent_name": "test-agent",
        "service_urls": {
            "test-service": "http://localhost:8000",
            "other-service": "http://localhost:8001",
        },
    }


@pytest.fixture
def wait_for_mock():
    """Mock asyncio.wait_for to avoid timeout issues.

    Returns:
        MagicMock: A mock for asyncio.wait_for that returns the awaited coroutine's result
    """

    async def mock_wait_for(coro, timeout):
        """Mock implementation that just awaits the coroutine."""
        return await coro

    with mock.patch("asyncio.wait_for", mock_wait_for):
        yield


@pytest.fixture
def base_communicator_context():
    """Set up a basic context for all communicator tests.

    This fixture creates a standard environment with:
    - Patched asyncio.wait_for
    - An agent_name
    - Standard service_urls
    - Handler registration helpers

    Returns:
        dict: Context dictionary with test components and utilities
    """
    # Create the context with explicit typing
    context: Dict[str, Any] = {
        "agent_name": "test-agent",
        "service_urls": {
            "test-service": "http://localhost:8000",
            "other-service": "http://localhost:8001",
        },
        "handlers": {},
    }

    # Add a simple handler registration utility with proper typing
    async def register_handler(method_name: str, handler: Callable[..., Awaitable[Any]]) -> None:
        handlers_dict = context["handlers"]
        if isinstance(handlers_dict, dict):
            handlers_dict[method_name] = handler

    context["register_handler"] = register_handler

    # Add a mock handler
    async def mock_handler(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"handler_result": "success", "args": args, "kwargs": kwargs}

    context["mock_handler"] = mock_handler

    # Mock asyncio.wait_for to avoid timeout issues
    async def mock_wait_for(coro, timeout):
        return await coro

    with mock.patch("asyncio.wait_for", mock_wait_for):
        yield context
