"""Mock-based tests for McpSseCommunicator.

These tests verify that the McpSseCommunicator component works correctly
without relying on actual network connections, by using mocks.
"""

import asyncio
from typing import Any, Dict
from unittest import mock

import pytest
from fastapi import FastAPI

from openmas.communication.mcp import McpSseCommunicator
from openmas.exceptions import CommunicationError, ServiceNotFoundError

# Mark all tests in this module with the 'mcp' marker
pytestmark = pytest.mark.mcp


@pytest.mark.asyncio
async def test_sse_communicator_direct_instantiation() -> None:
    """Test that McpSseCommunicator can be instantiated directly."""
    # Create a communicator with a custom app
    app = FastAPI(title="Test App")
    communicator = McpSseCommunicator(
        agent_name="test_agent",
        service_urls={"test_service": "http://localhost:8000/mcp"},
        server_mode=True,
        http_port=8000,
        app=app,
    )

    # Check that the communicator was created with the correct properties
    assert communicator.agent_name == "test_agent"
    assert communicator.service_urls == {"test_service": "http://localhost:8000/mcp"}
    assert communicator.server_mode is True
    assert communicator.http_port == 8000
    assert communicator.app is app


@pytest.mark.asyncio
@pytest.mark.timeout(5)  # Add a timeout to prevent hanging
async def test_sse_communicator_connect_client() -> None:
    """Test that the SSE communicator can connect to a service."""
    # Create a communicator
    communicator = McpSseCommunicator(
        agent_name="test_client",
        service_urls={"test_server": "http://localhost:8000/mcp"},
        server_mode=False,
    )

    # Create a mock session that will be returned by _connect_to_service
    mock_session = mock.AsyncMock()
    # Since we're testing test_method, it will be used as a tool name
    mock_session.call_tool.return_value = {"result": "success"}

    # Set up the sessions dict manually to avoid actually connecting
    communicator.sessions = {"test_server": mock_session}
    communicator.connected_services = {"test_server"}

    # Patch _connect_to_service to do nothing (since we've already set up the session)
    original_connect = communicator._connect_to_service
    communicator._connect_to_service = mock.AsyncMock()

    try:
        # Call send_request method that would normally try to connect
        result = await communicator.send_request(
            target_service="test_server",
            method="test_method",
            params={"a": 1, "b": 2},
        )

        # Verify the result
        assert result == {"result": "success"}

        # Check that _connect_to_service was called with the right parameters
        communicator._connect_to_service.assert_called_once_with("test_server")

        # Check that call_tool was called with the right parameters
        mock_session.call_tool.assert_called_once_with("test_method", arguments={"a": 1, "b": 2})
    finally:
        # Restore the original method to avoid affecting other tests
        communicator._connect_to_service = original_connect


@pytest.mark.asyncio
async def test_sse_communicator_send_request() -> None:
    """Test sending a request through the SSE communicator."""
    # Create a communicator
    communicator = McpSseCommunicator(
        agent_name="test_client",
        service_urls={"test_server": "http://localhost:8000/mcp"},
        server_mode=False,
    )

    # Mock the _connect_to_service method to avoid actually connecting
    communicator._connect_to_service = mock.AsyncMock()

    # Create a mock session
    mock_session = mock.AsyncMock()
    mock_session.call_tool.return_value = {"result": 42}

    # Store the mock session
    communicator.sessions = {"test_server": mock_session}
    communicator.connected_services.add("test_server")

    # Send a request
    result = await communicator.send_request(
        target_service="test_server",
        method="test_method",
        params={"a": 1, "b": 2},
    )

    # Verify that _connect_to_service was called
    communicator._connect_to_service.assert_called_once_with("test_server")

    # Verify that the session's call_tool was called with the right method name
    mock_session.call_tool.assert_called_once_with("test_method", arguments={"a": 1, "b": 2})

    # Verify the result
    assert result == {"result": 42}


@pytest.mark.asyncio
async def test_sse_communicator_call_tool() -> None:
    """Test calling a tool through the SSE communicator."""
    # Create a communicator
    communicator = McpSseCommunicator(
        agent_name="test_client",
        service_urls={"test_server": "http://localhost:8000/mcp"},
        server_mode=False,
    )

    # Set up mocks to avoid actual connection
    communicator._connect_to_service = mock.AsyncMock()

    # Create mock session
    mock_session = mock.AsyncMock()
    mock_session.call_tool.return_value = {"result": 42}

    # Store the mock session
    communicator.sessions = {"test_server": mock_session}
    communicator.connected_services.add("test_server")

    # Call a tool
    result = await communicator.call_tool(
        target_service="test_server",
        tool_name="test_tool",
        arguments={"a": 1, "b": 2},
    )

    # Verify that _connect_to_service was called
    communicator._connect_to_service.assert_called_once_with("test_server")

    # Verify that the session's call_tool was called with the right tool name
    mock_session.call_tool.assert_called_once_with("test_tool", arguments={"a": 1, "b": 2})

    # Verify the result
    assert result == {"result": 42}


@pytest.mark.asyncio
async def test_sse_communicator_server_methods() -> None:
    """Test that server-mode methods work correctly."""
    # Create a communicator in server mode
    app = FastAPI(title="Test App")
    communicator = McpSseCommunicator(
        agent_name="test_server",
        service_urls={},
        server_mode=True,
        http_port=8000,
        app=app,
    )

    # Create mock FastMCP instance with proper awaitable coroutines
    mock_server = mock.AsyncMock()
    
    # Create a completed Future instead of a dummy coroutine
    completed_future = asyncio.Future()
    completed_future.set_result(None)
    
    # Use the completed future as return values
    mock_server.add_tool.return_value = completed_future
    mock_server.add_prompt.return_value = completed_future
    mock_server.add_resource.return_value = completed_future

    # Mock methods to avoid actual server startup
    with mock.patch("mcp.server.fastmcp.FastMCP", return_value=mock_server):
        # Try to register a tool
        async def add(a: int, b: int) -> Dict[str, Any]:
            """Add two numbers."""
            return {"result": a + b}

        # Register the tool
        await communicator.register_tool("add", "Add two numbers", add)

        # Test tool registration when server is started
        communicator.server = mock_server
        await communicator.register_tool("add", "Add two numbers", add)
        mock_server.add_tool.assert_called_with(name="add", description="Add two numbers", fn=add)

        # Test prompt registration
        async def sample_prompt(topic: str) -> str:
            """Generate a sample prompt."""
            return f"Write about {topic}"

        await communicator.register_prompt("sample", "Sample prompt", sample_prompt)
        mock_server.add_prompt.assert_called_with(name="sample", description="Sample prompt", fn=sample_prompt)

        # Test resource registration
        async def sample_resource() -> bytes:
            """Return a sample resource."""
            return b"Sample resource"

        await communicator.register_resource("sample", "Sample resource", sample_resource, mime_type="text/plain")
        mock_server.add_resource.assert_called_with(
            uri="sample", description="Sample resource", fn=sample_resource, mime_type="text/plain"
        )


@pytest.mark.asyncio
async def test_sse_communicator_error_handling() -> None:
    """Test error handling in the SSE communicator."""
    # Create a communicator
    communicator = McpSseCommunicator(
        agent_name="test_client",
        service_urls={"test_server": "http://localhost:8000/mcp"},
        server_mode=False,
    )

    # Test service not found error
    with pytest.raises(ServiceNotFoundError) as excinfo:
        await communicator.send_request(
            target_service="nonexistent_service",
            method="test_method",
            params={"a": 1, "b": 2},
        )

    assert "nonexistent_service" in str(excinfo.value)

    # Test connection error
    communicator._connect_to_service = mock.AsyncMock(
        side_effect=CommunicationError("Connection failed", target="test_server")
    )

    with pytest.raises(CommunicationError) as excinfo:
        await communicator.send_request(
            target_service="test_server",
            method="test_method",
            params={"a": 1, "b": 2},
        )

    assert "Connection failed" in str(excinfo.value)

    # Test method call error
    communicator._connect_to_service = mock.AsyncMock()  # Reset the mock
    mock_session = mock.AsyncMock()
    mock_session.call_tool.side_effect = Exception("Method call failed")
    communicator.sessions = {"test_server": mock_session}
    communicator.connected_services.add("test_server")

    with pytest.raises(CommunicationError) as excinfo:
        await communicator.send_request(
            target_service="test_server",
            method="test_method",
            params={"a": 1, "b": 2},
        )

    assert "Method call failed" in str(excinfo.value)
