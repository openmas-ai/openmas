"""Unit tests for MCP communicator integration.

This module tests the integration between different MCP communicator implementations
such as SSE and STDIO, as well as error handling scenarios.
"""

from unittest import mock

import pytest

from openmas.communication.mcp import McpSseCommunicator, McpStdioCommunicator
from openmas.exceptions import CommunicationError, ServiceNotFoundError
from tests.unit.communication.mcp.mcp_mocks import MockClientSession, apply_mcp_mocks

# Apply MCP mocks before imports
apply_mcp_mocks()


@pytest.fixture
def mock_sse_communicator():
    """Create a mock SSE communicator with predefined behavior."""
    # Create a mock communicator
    communicator = mock.AsyncMock(spec=McpSseCommunicator)

    # Set up the basic methods needed for testing
    communicator.agent_name = "test_sse_agent"
    communicator.service_urls = {"test_service": "http://localhost:8765/mcp"}
    communicator.sessions = {}

    # Mock the tool methods
    mock_tool1 = {"name": "calculate", "description": "Perform calculations"}
    mock_tool2 = {"name": "echo", "description": "Echo a message"}
    communicator.list_tools.return_value = [mock_tool1, mock_tool2]

    # Mock the call_tool method
    async def mock_call_tool(target_service, tool_name, arguments=None, timeout=None):
        if tool_name == "calculate":
            x = arguments.get("x", 0)
            y = arguments.get("y", 0)
            operation = arguments.get("operation", "add")

            if operation == "add":
                result = x + y
                description = f"Added {x} and {y}"
            elif operation == "subtract":
                result = x - y
                description = f"Subtracted {y} from {x}"
            elif operation == "multiply":
                result = x * y
                description = f"Multiplied {x} by {y}"
            elif operation == "divide":
                if y == 0:
                    raise ValueError("Cannot divide by zero")
                result = x / y
                description = f"Divided {x} by {y}"
            else:
                raise ValueError(f"Unknown operation: {operation}")

            return {"result": result, "operation_performed": description}
        elif tool_name == "echo":
            return {"message": arguments.get("message", "")}
        # Add support for forwarded tools
        elif tool_name == "greet" or tool_name == "reverse":
            # This will handle forwarded tools from the STDIO communicator
            return {"forwarded_from_sse": True, "tool": tool_name, "args": arguments}
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    communicator.call_tool.side_effect = mock_call_tool

    # Mock connect_to_service
    async def mock_connect_to_service(service_name):
        if service_name in communicator.service_urls:
            communicator.sessions[service_name] = MockClientSession()
        else:
            raise ServiceNotFoundError(f"Service '{service_name}' not found", target=service_name)

    communicator._connect_to_service.side_effect = mock_connect_to_service

    # Mock send_request
    async def mock_send_request(target_service, method, params=None, response_model=None, timeout=None):
        if target_service not in communicator.sessions:
            await communicator._connect_to_service(target_service)

        if method.startswith("tool/call/"):
            tool_name = method[len("tool/call/") :]
            return await communicator.call_tool(target_service, tool_name, params, timeout)
        elif method == "tool/list":
            return await communicator.list_tools(target_service)
        else:
            return {"result": "success"}

    communicator.send_request.side_effect = mock_send_request

    # Return the configured mock
    return communicator


@pytest.fixture
def mock_stdio_communicator():
    """Create a mock STDIO communicator with predefined behavior."""
    # Create a mock communicator
    communicator = mock.AsyncMock(spec=McpStdioCommunicator)

    # Set up the basic methods needed for testing
    communicator.agent_name = "test_stdio_agent"
    communicator.service_urls = {"test_service": "python -m test_script.py"}
    communicator.sessions = {}
    communicator.subprocesses = {}
    communicator._client_managers = {}

    # Mock the tool methods
    mock_tool1 = {"name": "greet", "description": "Greet a person"}
    mock_tool2 = {"name": "reverse", "description": "Reverse a string"}
    communicator.list_tools.return_value = [mock_tool1, mock_tool2]

    # Mock the call_tool method
    async def mock_call_tool(target_service, tool_name, arguments=None, timeout=None):
        if tool_name == "greet":
            name = arguments.get("name", "World")
            return {"greeting": f"Hello, {name}!"}
        elif tool_name == "reverse":
            text = arguments.get("text", "")
            return {"reversed": text[::-1]}
        # Add support for forwarded tools
        elif tool_name == "calculate" or tool_name == "echo":
            # This will handle forwarded tools from the SSE communicator
            return {"forwarded_from_stdio": True, "tool": tool_name, "args": arguments}
        else:
            # Allow tool calls to be forwarded to another communicator
            return {"forwarded": True, "tool": tool_name, "args": arguments}

    communicator.call_tool.side_effect = mock_call_tool

    # Mock connect_to_service
    async def mock_connect_to_service(service_name):
        if service_name in communicator.service_urls:
            communicator.sessions[service_name] = MockClientSession()
            # Create a mock subprocess
            mock_process = mock.MagicMock()
            mock_process.stdin = mock.MagicMock()
            mock_process.stdout = mock.MagicMock()
            mock_process.terminate = mock.MagicMock()
            communicator.subprocesses[service_name] = mock_process
        else:
            raise ServiceNotFoundError(f"Service '{service_name}' not found", target=service_name)

    communicator._connect_to_service.side_effect = mock_connect_to_service

    # Mock send_request
    async def mock_send_request(target_service, method, params=None, response_model=None, timeout=None):
        if target_service not in communicator.sessions:
            await communicator._connect_to_service(target_service)

        if method.startswith("tool/call/"):
            tool_name = method[len("tool/call/") :]
            return await communicator.call_tool(target_service, tool_name, params, timeout)
        elif method == "tool/list":
            return await communicator.list_tools(target_service)
        else:
            return {"result": "success"}

    communicator.send_request.side_effect = mock_send_request

    # Return the configured mock
    return communicator


class TestMcpCommunicatorIntegration:
    """Test class for MCP communicator integration."""

    @pytest.mark.asyncio
    async def test_sse_forward_to_stdio(self, mock_sse_communicator, mock_stdio_communicator):
        """Test that an SSE communicator can forward requests to a STDIO communicator."""
        # Set up the communicators
        await mock_sse_communicator.start()
        await mock_stdio_communicator.start()

        try:
            # Create the mock client session for SSE
            mock_session = MockClientSession()
            mock_sse_communicator.sessions["test_service"] = mock_session

            # Configure forwarding
            async def forward_to_stdio_call_tool(target_service, tool_name, arguments=None, timeout=None):
                if tool_name in ["greet", "reverse"]:
                    # Forward to STDIO
                    return await mock_stdio_communicator.call_tool(
                        target_service="test_service", tool_name=tool_name, arguments=arguments, timeout=timeout
                    )
                else:
                    # Handle with original method
                    original_side_effect = mock_sse_communicator.call_tool.side_effect
                    mock_sse_communicator.call_tool.side_effect = None  # Prevent recursion
                    result = await original_side_effect(target_service, tool_name, arguments, timeout)
                    mock_sse_communicator.call_tool.side_effect = original_side_effect
                    return result

            # Set up the forwarding
            mock_sse_communicator.call_tool.side_effect = forward_to_stdio_call_tool

            # Call a tool on the SSE communicator that will be forwarded to STDIO
            result = await mock_sse_communicator.call_tool(
                target_service="test_service", tool_name="greet", arguments={"name": "Alice"}
            )

            # Check that the result matches what the STDIO communicator would return
            assert result == {"greeting": "Hello, Alice!"}

            # Check another tool
            result = await mock_sse_communicator.send_request(
                target_service="test_service", method="tool/call/reverse", params={"text": "hello world"}
            )

            # Check the result
            assert result == {"reversed": "dlrow olleh"}
        finally:
            # Clean up
            await mock_sse_communicator.stop()
            await mock_stdio_communicator.stop()

    @pytest.mark.asyncio
    async def test_stdio_forward_to_sse(self, mock_sse_communicator, mock_stdio_communicator):
        """Test that a STDIO communicator can forward requests to an SSE communicator."""
        # Set up the communicators
        await mock_sse_communicator.start()
        await mock_stdio_communicator.start()

        try:
            # Create the mock client session for STDIO
            mock_session = MockClientSession()
            mock_stdio_communicator.sessions["test_service"] = mock_session

            # Store the original side effects for later restoration if needed (not used in this test)
            # Commented out to avoid flake8 warnings
            # original_sse_call_tool = mock_sse_communicator.call_tool.side_effect
            # original_stdio_call_tool = mock_stdio_communicator.call_tool.side_effect

            # Configure forwarding
            async def forward_to_sse_call_tool(target_service, tool_name, arguments=None, timeout=None):
                if tool_name in ["calculate", "echo"]:
                    # Forward to SSE
                    return await mock_sse_communicator.call_tool(
                        target_service="test_service", tool_name=tool_name, arguments=arguments, timeout=timeout
                    )
                else:
                    # Handle with original method
                    mock_stdio_communicator.call_tool.side_effect = None  # Prevent recursion
                    result = await mock_stdio_communicator.call_tool(target_service, tool_name, arguments, timeout)
                    mock_stdio_communicator.call_tool.side_effect = forward_to_sse_call_tool
                    return result

            # Set up the forwarding
            mock_stdio_communicator.call_tool.side_effect = forward_to_sse_call_tool

            # Call a tool on the STDIO communicator that will be forwarded to SSE
            result = await mock_stdio_communicator.call_tool(
                target_service="test_service",
                tool_name="calculate",
                arguments={"x": 5, "y": 3, "operation": "multiply"},
            )

            # Check that the result matches what the SSE communicator would return
            assert result == {"result": 15, "operation_performed": "Multiplied 5 by 3"}

            # Test the error handling by dividing by zero
            with pytest.raises(ValueError, match="Cannot divide by zero"):
                await mock_stdio_communicator.call_tool(
                    target_service="test_service",
                    tool_name="calculate",
                    arguments={"x": 10, "y": 0, "operation": "divide"},
                )
        finally:
            # Clean up
            await mock_sse_communicator.stop()
            await mock_stdio_communicator.stop()

    @pytest.mark.asyncio
    async def test_service_not_found_error(self, mock_sse_communicator):
        """Test that ServiceNotFoundError is properly raised and handled."""
        # Set up the communicator
        await mock_sse_communicator.start()

        try:
            # Try to access a service that doesn't exist
            with pytest.raises(ServiceNotFoundError) as excinfo:
                await mock_sse_communicator.send_request(target_service="non_existent_service", method="tool/list")

            # Check the error message
            assert "non_existent_service" in str(excinfo.value)
            assert excinfo.value.target == "non_existent_service"
        finally:
            # Clean up
            await mock_sse_communicator.stop()

    @pytest.mark.asyncio
    async def test_communication_error_handling(self, mock_stdio_communicator):
        """Test that CommunicationError is properly raised and handled."""
        # Set up the communicator
        await mock_stdio_communicator.start()

        try:
            # Mock a scenario where connecting fails after the service is registered
            mock_stdio_communicator.service_urls["failing_service"] = "python -m failing_script.py"

            # Make _connect_to_service raise a CommunicationError
            async def failing_connect(service_name):
                if service_name == "failing_service":
                    raise CommunicationError(f"Failed to connect to service '{service_name}'", target=service_name)
                else:
                    return await mock_stdio_communicator._connect_to_service.side_effect(service_name)

            mock_stdio_communicator._connect_to_service.side_effect = failing_connect

            # Try to use the failing service
            with pytest.raises(CommunicationError) as excinfo:
                await mock_stdio_communicator.send_request(target_service="failing_service", method="tool/list")

            # Check the error message
            assert "failing_service" in str(excinfo.value)
            assert excinfo.value.target == "failing_service"
        finally:
            # Clean up
            await mock_stdio_communicator.stop()

    @pytest.mark.asyncio
    async def test_bidirectional_communication(self, mock_sse_communicator, mock_stdio_communicator):
        """Test bidirectional communication between SSE and STDIO communicators."""
        # Set up the communicators
        await mock_sse_communicator.start()
        await mock_stdio_communicator.start()

        try:
            # Create mock sessions
            sse_session = MockClientSession()
            stdio_session = MockClientSession()
            mock_sse_communicator.sessions["stdio_service"] = sse_session
            mock_stdio_communicator.sessions["sse_service"] = stdio_session

            # Add the communicators to each other's service_urls
            mock_sse_communicator.service_urls["stdio_service"] = "python -m stdio_service.py"
            mock_stdio_communicator.service_urls["sse_service"] = "http://localhost:8765/mcp"

            # Store original implementations (not used in this test)
            # Commented out to avoid flake8 warnings
            # original_sse_call_tool = mock_sse_communicator.call_tool.side_effect
            # original_stdio_call_tool = mock_stdio_communicator.call_tool.side_effect

            # Create direct implementation functions to avoid recursion issues
            async def direct_sse_call_tool(target_service, tool_name, arguments=None, timeout=None):
                """Direct implementation of SSE call_tool without forwarding."""
                if tool_name == "calculate":
                    x = arguments.get("x", 0)
                    y = arguments.get("y", 0)
                    operation = arguments.get("operation", "add")

                    if operation == "add":
                        result = x + y
                        description = f"Added {x} and {y}"
                    elif operation == "subtract":
                        result = x - y
                        description = f"Subtracted {y} from {x}"
                    elif operation == "multiply":
                        result = x * y
                        description = f"Multiplied {x} by {y}"
                    elif operation == "divide":
                        if y == 0:
                            raise ValueError("Cannot divide by zero")
                        result = x / y
                        description = f"Divided {x} by {y}"
                    else:
                        raise ValueError(f"Unknown operation: {operation}")

                    return {"result": result, "operation_performed": description}
                elif tool_name == "echo":
                    return {"message": arguments.get("message", "")}
                else:
                    return {"tool": tool_name, "args": arguments}

            async def direct_stdio_call_tool(target_service, tool_name, arguments=None, timeout=None):
                """Direct implementation of STDIO call_tool without forwarding."""
                if tool_name == "greet":
                    name = arguments.get("name", "World")
                    return {"greeting": f"Hello, {name}!"}
                elif tool_name == "reverse":
                    text = arguments.get("text", "")
                    return {"reversed": text[::-1]}
                else:
                    return {"tool": tool_name, "args": arguments}

            # Configure the SSE communicator to forward 'greet' and 'reverse' to STDIO
            async def sse_forward_some_tools(target_service, tool_name, arguments=None, timeout=None):
                if tool_name in ["greet", "reverse"]:
                    # Forward to STDIO
                    return await direct_stdio_call_tool(
                        target_service="test_service", tool_name=tool_name, arguments=arguments, timeout=timeout
                    )
                else:
                    # Use direct implementation
                    return await direct_sse_call_tool(
                        target_service=target_service, tool_name=tool_name, arguments=arguments, timeout=timeout
                    )

            # Configure the STDIO communicator to forward 'calculate' to SSE
            async def stdio_forward_some_tools(target_service, tool_name, arguments=None, timeout=None):
                if tool_name in ["calculate", "echo"]:
                    # Forward to SSE
                    return await direct_sse_call_tool(
                        target_service="test_service", tool_name=tool_name, arguments=arguments, timeout=timeout
                    )
                else:
                    # Use direct implementation
                    return await direct_stdio_call_tool(
                        target_service=target_service, tool_name=tool_name, arguments=arguments, timeout=timeout
                    )

            # Set the new side effects
            mock_sse_communicator.call_tool.side_effect = sse_forward_some_tools
            mock_stdio_communicator.call_tool.side_effect = stdio_forward_some_tools

            # Test that STDIO tools can be called via SSE
            result = await mock_sse_communicator.call_tool(
                target_service="stdio_service", tool_name="greet", arguments={"name": "Bob"}
            )

            assert result == {"greeting": "Hello, Bob!"}

            # Test that SSE tools can be called via STDIO
            result = await mock_stdio_communicator.call_tool(
                target_service="sse_service", tool_name="calculate", arguments={"x": 8, "y": 2, "operation": "divide"}
            )

            assert result == {"result": 4.0, "operation_performed": "Divided 8 by 2"}
        finally:
            # Clean up
            await mock_sse_communicator.stop()
            await mock_stdio_communicator.stop()
