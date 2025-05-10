"""Unit tests for McpClientAgent class."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openmas.agent.mcp_client import McpClientAgent
from openmas.config import AgentConfig
from openmas.exceptions import CommunicationError


@pytest.fixture
def client_agent():
    """Create a test client agent with a mock communicator."""
    with patch("pathlib.Path.cwd", return_value=Path("/fake/path")):
        config = AgentConfig(name="test_client")
        agent = McpClientAgent(config=config)
        agent.communicator = MagicMock()
        agent.communicator.service_urls = {}
        # Add connected_services attribute to test disconnection logic
        agent.communicator.connected_services = set()
        return agent


@pytest.mark.asyncio
async def test_connect_to_service_sse(client_agent):
    """Test connecting to a service using SSE protocol."""
    # Set up the communicator mock
    client_agent.communicator._connect_to_service = AsyncMock()

    # Call the method
    await client_agent.connect_to_service("test_service", "localhost", 8000, "sse")

    # Verify the service URL was added correctly
    assert client_agent.communicator.service_urls["test_service"] == "http://localhost:8000/mcp"
    # Verify connection was attempted
    client_agent.communicator._connect_to_service.assert_called_once_with("test_service")


@pytest.mark.asyncio
async def test_connect_to_service_stdio(client_agent):
    """Test connecting to a service using stdio protocol."""
    # Set up the communicator mock
    client_agent.communicator._connect_to_service = AsyncMock()

    # Call the method
    await client_agent.connect_to_service("test_service", "localhost", 8000, "stdio")

    # Verify the service URL was added correctly
    assert client_agent.communicator.service_urls["test_service"] == "stdio://localhost:8000"
    # Verify connection was attempted
    client_agent.communicator._connect_to_service.assert_called_once_with("test_service")


@pytest.mark.asyncio
async def test_connect_to_service_invalid_protocol(client_agent):
    """Test connecting to a service with invalid protocol."""
    # Call the method with an invalid protocol
    with pytest.raises(ValueError, match="Unsupported protocol: invalid"):
        await client_agent.connect_to_service("test_service", "localhost", 8000, "invalid")


@pytest.mark.asyncio
async def test_connect_to_service_no_communicator():
    """Test connecting to a service without a communicator."""
    # Create an agent without a communicator
    with patch("pathlib.Path.cwd", return_value=Path("/fake/path")):
        config = AgentConfig(name="test_client")
        agent = McpClientAgent(config=config)
        agent.communicator = None

    # Call the method should raise an error
    with pytest.raises(RuntimeError, match="Agent must have a communicator set before connecting to services"):
        await agent.connect_to_service("test_service", "localhost", 8000, "sse")


@pytest.mark.asyncio
async def test_connect_to_service_connection_error(client_agent):
    """Test connecting to a service that raises a connection error."""
    # Set up the communicator mock to raise an error
    client_agent.communicator._connect_to_service = AsyncMock(
        side_effect=CommunicationError("Failed to connect to service")
    )

    # Call the method should propagate the error but remove the service URL
    with pytest.raises(CommunicationError, match="Failed to connect to service"):
        await client_agent.connect_to_service("test_service", "localhost", 8000, "sse")

    # Verify the service URL was removed after the error
    assert "test_service" not in client_agent.communicator.service_urls


@pytest.mark.asyncio
async def test_disconnect_from_service_with_cleanup_method(client_agent):
    """Test disconnecting from a service with _cleanup_client_manager method."""
    # Add service to connected_services
    client_agent.communicator.connected_services.add("test_service")
    client_agent.communicator.service_urls["test_service"] = "http://localhost:8000/mcp"

    # Set up hasattr mock
    with patch("openmas.agent.mcp_client.hasattr") as mock_hasattr:
        # Configure hasattr to return True for _cleanup_client_manager and False for others
        def hasattr_side_effect(obj, attr):
            return attr == "_cleanup_client_manager"

        mock_hasattr.side_effect = hasattr_side_effect

        # Add cleanup method
        client_agent.communicator._cleanup_client_manager = AsyncMock()

        # Call the method
        await client_agent.disconnect_from_service("test_service")

        # Verify the method was called
        client_agent.communicator._cleanup_client_manager.assert_called_once_with("test_service")


@pytest.mark.asyncio
async def test_disconnect_from_service_with_disconnect_method(client_agent):
    """Test disconnecting from a service with _disconnect_from_service method."""
    # Add service to connected_services
    client_agent.communicator.connected_services.add("test_service")
    client_agent.communicator.service_urls["test_service"] = "http://localhost:8000/mcp"

    # Set up hasattr mock
    with patch("openmas.agent.mcp_client.hasattr") as mock_hasattr:
        # Configure hasattr to return True for _disconnect_from_service and False for others
        def hasattr_side_effect(obj, attr):
            return attr == "_disconnect_from_service"

        mock_hasattr.side_effect = hasattr_side_effect

        # Add disconnect method
        client_agent.communicator._disconnect_from_service = AsyncMock()

        # Call the method
        await client_agent.disconnect_from_service("test_service")

        # Verify the method was called
        client_agent.communicator._disconnect_from_service.assert_called_once_with("test_service")


@pytest.mark.asyncio
async def test_disconnect_from_service_fallback(client_agent):
    """Test disconnecting from a service using the fallback method."""
    # Create a custom mock for connected_services that will track removal
    mock_connected_services = MagicMock()
    mock_connected_services.__contains__ = lambda self, item: item == "test_service"
    mock_connected_services.remove = MagicMock()

    # Set the mock on the communicator
    client_agent.communicator.connected_services = mock_connected_services
    client_agent.communicator.service_urls["test_service"] = "http://localhost:8000/mcp"

    # Set up hasattr mock to return False for cleanup methods but True for connected_services attribute
    with patch("openmas.agent.mcp_client.hasattr") as mock_hasattr:

        def hasattr_side_effect(obj, attr):
            if attr == "connected_services":
                return True
            return False

        mock_hasattr.side_effect = hasattr_side_effect

        # Call the method
        await client_agent.disconnect_from_service("test_service")

        # Verify that remove was called on the connected_services
        mock_connected_services.remove.assert_called_once_with("test_service")


@pytest.mark.asyncio
async def test_disconnect_from_service_exception(client_agent):
    """Test disconnecting from a service that raises an exception."""
    # Add service to connected_services
    client_agent.communicator.connected_services.add("test_service")
    client_agent.communicator.service_urls["test_service"] = "http://localhost:8000/mcp"

    # Set up hasattr mock
    with patch("openmas.agent.mcp_client.hasattr") as mock_hasattr:
        # Configure hasattr to return True for _disconnect_from_service
        def hasattr_side_effect(obj, attr):
            return attr == "_disconnect_from_service"

        mock_hasattr.side_effect = hasattr_side_effect

        # Add disconnect method that raises an exception
        error = Exception("Failed to disconnect")
        client_agent.communicator._disconnect_from_service = AsyncMock(side_effect=error)

        # Call the method - should not raise exception but log warning
        await client_agent.disconnect_from_service("test_service")

        # Verify the method was called
        client_agent.communicator._disconnect_from_service.assert_called_once_with("test_service")


@pytest.mark.asyncio
async def test_list_tools_with_communicator_method(client_agent):
    """Test listing tools when communicator has list_tools method."""
    # Set up the mock response
    tools = [
        {"name": "test_tool", "description": "A test tool"},
        {"name": "another_tool", "description": "Another test tool"},
    ]

    # Add list_tools method
    client_agent.communicator.list_tools = AsyncMock(return_value=tools)

    # Call the method
    result = await client_agent.list_tools("test_service")

    # Verify the result
    assert result == tools
    client_agent.communicator.list_tools.assert_called_once_with("test_service")


@pytest.mark.asyncio
async def test_list_tools_with_send_request_fallback(client_agent):
    """Test listing tools using send_request fallback."""
    # Set up the mock response
    tools = [
        {"name": "test_tool", "description": "A test tool"},
        {"name": "another_tool", "description": "Another test tool"},
    ]

    # Add send_request method instead of list_tools
    client_agent.communicator.send_request = AsyncMock(return_value=tools)

    # Set up hasattr mock to indicate list_tools is not available
    with patch("openmas.agent.mcp_client.hasattr", lambda obj, attr: attr != "list_tools"):
        # Call the method
        result = await client_agent.list_tools("test_service")

        # Verify the result
        assert result == tools
        client_agent.communicator.send_request.assert_called_once_with(
            target_service="test_service",
            method="tool/list",
        )


@pytest.mark.asyncio
async def test_list_tools_with_tools_in_dict(client_agent):
    """Test listing tools when the response has tools in a dict."""
    # Set up the mock response with tools in a dict
    tools_dict = {
        "tools": [
            {"name": "test_tool", "description": "A test tool"},
            {"name": "another_tool", "description": "Another test tool"},
        ]
    }

    # Add send_request method
    client_agent.communicator.send_request = AsyncMock(return_value=tools_dict)

    # Set up hasattr mock to indicate list_tools is not available
    with patch("openmas.agent.mcp_client.hasattr", lambda obj, attr: attr != "list_tools"):
        # Call the method
        result = await client_agent.list_tools("test_service")

        # Verify the result - should extract tools from dict
        assert len(result) == 2
        assert result[0]["name"] == "test_tool"
        assert result[1]["name"] == "another_tool"


@pytest.mark.asyncio
async def test_list_tools_unexpected_format(client_agent):
    """Test listing tools when the response has an unexpected format."""
    # Set up the mock response with unexpected format
    unexpected_response = "not a list or dict"

    # Add send_request method
    client_agent.communicator.send_request = AsyncMock(return_value=unexpected_response)

    # Set up hasattr mock to indicate list_tools is not available
    with patch("openmas.agent.mcp_client.hasattr", lambda obj, attr: attr != "list_tools"):
        # Call the method
        result = await client_agent.list_tools("test_service")

        # Verify the result - should return empty list for unexpected format
        assert result == []


@pytest.mark.asyncio
async def test_list_prompts(client_agent):
    """Test listing prompts."""
    # Set up the mock response
    prompts = [
        {"name": "test_prompt", "description": "A test prompt"},
        {"name": "another_prompt", "description": "Another test prompt"},
    ]

    # Add send_request method
    client_agent.communicator.send_request = AsyncMock(return_value=prompts)

    # Call the method
    result = await client_agent.list_prompts("test_service")

    # Verify the result
    assert result == prompts
    client_agent.communicator.send_request.assert_called_once_with(
        target_service="test_service",
        method="prompt/list",
    )


@pytest.mark.asyncio
async def test_list_prompts_with_prompts_in_dict(client_agent):
    """Test listing prompts when the response has prompts in a dict."""
    # Set up the mock response with prompts in a dict
    prompts_dict = {
        "prompts": [
            {"name": "test_prompt", "description": "A test prompt"},
            {"name": "another_prompt", "description": "Another test prompt"},
        ]
    }

    # Add send_request method
    client_agent.communicator.send_request = AsyncMock(return_value=prompts_dict)

    # Call the method
    result = await client_agent.list_prompts("test_service")

    # Verify the result - should extract prompts from dict
    assert len(result) == 2
    assert result[0]["name"] == "test_prompt"
    assert result[1]["name"] == "another_prompt"


@pytest.mark.asyncio
async def test_list_prompts_error(client_agent):
    """Test listing prompts when an error occurs."""
    # Set up the communicator mock to raise an error
    client_agent.communicator.send_request = AsyncMock(side_effect=CommunicationError("Failed to list prompts"))

    # Call the method should propagate the error
    with pytest.raises(CommunicationError, match="Failed to list prompts"):
        await client_agent.list_prompts("test_service")


@pytest.mark.asyncio
async def test_list_resources(client_agent):
    """Test listing resources."""
    # Set up the mock response
    resources = [
        {"name": "test_resource", "description": "A test resource", "uri": "/test/resource"},
        {"name": "another_resource", "description": "Another test resource", "uri": "/another/resource"},
    ]

    # Add send_request method
    client_agent.communicator.send_request = AsyncMock(return_value=resources)

    # Call the method
    result = await client_agent.list_resources("test_service")

    # Verify the result
    assert result == resources
    client_agent.communicator.send_request.assert_called_once_with(
        target_service="test_service",
        method="resource/list",
    )


@pytest.mark.asyncio
async def test_list_resources_with_resources_in_dict(client_agent):
    """Test listing resources when the response has resources in a dict."""
    # Set up the mock response with resources in a dict
    resources_dict = {
        "resources": [
            {"name": "test_resource", "description": "A test resource", "uri": "/test/resource"},
            {"name": "another_resource", "description": "Another test resource", "uri": "/another/resource"},
        ]
    }

    # Add send_request method
    client_agent.communicator.send_request = AsyncMock(return_value=resources_dict)

    # Call the method
    result = await client_agent.list_resources("test_service")

    # Verify the result - should extract resources from dict
    assert len(result) == 2
    assert result[0]["name"] == "test_resource"
    assert result[1]["name"] == "another_resource"


@pytest.mark.asyncio
async def test_call_tool_with_communicator_method(client_agent):
    """Test calling a tool when communicator has call_tool method."""
    # Set up the mock response
    result = {"result": "success"}

    # Add call_tool method
    client_agent.communicator.call_tool = AsyncMock(return_value=result)

    # Call the method
    response = await client_agent.call_tool(
        target_service="test_service", tool_name="test_tool", arguments={"param": "value"}, timeout=10.0
    )

    # Verify the result
    assert response == result
    client_agent.communicator.call_tool.assert_called_once_with(
        target_service="test_service", tool_name="test_tool", arguments={"param": "value"}, timeout=10.0
    )


@pytest.mark.asyncio
async def test_call_tool_with_send_request_fallback(client_agent):
    """Test calling a tool using send_request fallback."""
    # Set up the mock response
    result = {"result": "success"}

    # Add send_request method
    client_agent.communicator.send_request = AsyncMock(return_value=result)

    # Set up hasattr mock to indicate call_tool is not available
    with patch("openmas.agent.mcp_client.hasattr", lambda obj, attr: attr != "call_tool"):
        # Call the method
        response = await client_agent.call_tool(
            target_service="test_service", tool_name="test_tool", arguments={"param": "value"}, timeout=10.0
        )

        # Verify the result
        assert response == result.get("result", result)
        client_agent.communicator.send_request.assert_called_once_with(
            target_service="test_service", method="tool/call/test_tool", params={"param": "value"}, timeout=10.0
        )


@pytest.mark.asyncio
async def test_get_prompt(client_agent):
    """Test getting a prompt."""
    # Set up the mock response
    response = "Hello, {{ name }}!"

    # Add get_prompt method using AsyncMock
    client_agent.communicator.get_prompt = AsyncMock(return_value=response)

    # Add send_request method as fallback
    client_agent.communicator.send_request = AsyncMock(return_value=response)

    # Call the method
    result = await client_agent.get_prompt(
        target_service="test_service", prompt_name="greeting", arguments={"name": "User"}, timeout=10.0
    )

    # Verify the result
    assert result == response
    client_agent.communicator.get_prompt.assert_called_once_with(
        target_service="test_service", prompt_name="greeting", arguments={"name": "User"}, timeout=10.0
    )
    # Verify send_request was not called since get_prompt was available
    client_agent.communicator.send_request.assert_not_called()


@pytest.mark.asyncio
async def test_read_resource(client_agent):
    """Test reading a resource."""
    # Set up the mock response
    resource_content = b'{"data": "test"}'

    # Add read_resource method using AsyncMock
    client_agent.communicator.read_resource = AsyncMock(return_value=resource_content)

    # Add send_request method as fallback
    client_agent.communicator.send_request = AsyncMock(return_value=resource_content)

    # Call the method
    result = await client_agent.read_resource(target_service="test_service", uri="/test/resource", timeout=10.0)

    # Verify the result
    assert result == resource_content
    client_agent.communicator.read_resource.assert_called_once_with(
        target_service="test_service", resource_uri="/test/resource", timeout=10.0
    )
    # Verify send_request was not called since read_resource was available
    client_agent.communicator.send_request.assert_not_called()


@pytest.mark.asyncio
async def test_read_resource_string_conversion(client_agent):
    """Test reading a resource with string result that gets converted to bytes."""
    # Set up the mock response as a string
    resource_content = '{"data": "test"}'

    # Add read_resource method using AsyncMock that returns a string (which will be converted to bytes)
    client_agent.communicator.read_resource = AsyncMock(return_value=resource_content)

    # Add send_request method as fallback
    client_agent.communicator.send_request = AsyncMock(return_value=resource_content)

    # Call the method
    result = await client_agent.read_resource(target_service="test_service", uri="/test/resource")

    # Verify the result is converted to bytes
    assert isinstance(result, bytes)
    assert result == b'{"data": "test"}'
    client_agent.communicator.read_resource.assert_called_once_with(
        target_service="test_service", resource_uri="/test/resource", timeout=None
    )
    # Verify send_request was not called since read_resource was available
    client_agent.communicator.send_request.assert_not_called()


@pytest.mark.asyncio
async def test_sample_prompt(client_agent):
    """Test sampling a prompt."""
    # Set up the mock response
    response = {"content": "This is a generated response", "model": "test-model", "complete": True}

    # Set up messages
    messages = [{"role": "user", "content": "Hello, how are you?"}]

    # Add sample_prompt method
    client_agent.communicator.sample_prompt = AsyncMock(return_value=response)

    # Mock the isinstance check to return True for McpCommunicatorProtocol
    with patch("openmas.agent.mcp.isinstance", return_value=True):
        # Call the method
        result = await client_agent.sample_prompt(
            target_service="test_service",
            messages=messages,
            system_prompt="You are a helpful assistant",
            temperature=0.7,
            max_tokens=100,
            include_context="minimal",
            model_preferences={"model": "test-model"},
            stop_sequences=["STOP"],
            timeout=30.0,
        )

        # Verify the result
        assert result == response
        client_agent.communicator.sample_prompt.assert_called_once_with(
            target_service="test_service",
            messages=messages,
            system_prompt="You are a helpful assistant",
            temperature=0.7,
            max_tokens=100,
            include_context="minimal",
            model_preferences={"model": "test-model"},
            stop_sequences=["STOP"],
            timeout=30.0,
        )


@pytest.mark.asyncio
async def test_sample_prompt_minimal_params(client_agent):
    """Test sampling a prompt with minimal parameters."""
    # Set up the mock response
    response = {"content": "This is a generated response", "complete": True}

    # Set up messages
    messages = [{"role": "user", "content": "Hello, how are you?"}]

    # Add sample_prompt method
    client_agent.communicator.sample_prompt = AsyncMock(return_value=response)

    # Mock the isinstance check to return True for McpCommunicatorProtocol
    with patch("openmas.agent.mcp.isinstance", return_value=True):
        # Call the method with minimal parameters
        result = await client_agent.sample_prompt(target_service="test_service", messages=messages)

        # Verify the result
        assert result == response
        client_agent.communicator.sample_prompt.assert_called_once_with(
            target_service="test_service",
            messages=messages,
            system_prompt=None,
            temperature=None,
            max_tokens=None,
            include_context=None,
            model_preferences=None,
            stop_sequences=None,
            timeout=None,
        )
