"""Tests for unified communication between different MCP communicator types.

This module tests the ability to create a unified communication system
where tools and resources from different communicator types (SSE and STDIO)
can be shared and accessed through a single interface.
"""

from unittest import mock

import pytest

from openmas.communication.mcp import McpSseCommunicator, McpStdioCommunicator
from openmas.exceptions import CommunicationError, ServiceNotFoundError
from tests.unit.communication.mcp.mcp_mocks import MockClientSession, apply_mcp_mocks

# Apply MCP mocks before imports
apply_mcp_mocks()


class UnifiedCommunicationAgent:
    """Mock agent that manages multiple communicator types for unified communication.

    This is a simplified mock version that doesn't inherit from McpAgent to avoid
    configuration loading issues in tests.
    """

    def __init__(self, name="unified_agent"):
        """Initialize the agent with both SSE and STDIO communicators."""
        self.name = name
        self.sse_communicator = None
        self.stdio_communicator = None
        self.communicator = None  # Primary communicator

    def setup_communicators(self):
        """Set up the SSE and STDIO communicators."""
        # Create mocked SSE communicator
        self.sse_communicator = mock.AsyncMock(spec=McpSseCommunicator)
        self.sse_communicator.agent_name = self.name
        self.sse_communicator.service_urls = {}
        self.sse_communicator.sessions = {}

        # Create mocked STDIO communicator
        self.stdio_communicator = mock.AsyncMock(spec=McpStdioCommunicator)
        self.stdio_communicator.agent_name = self.name
        self.stdio_communicator.service_urls = {}
        self.stdio_communicator.sessions = {}
        self.stdio_communicator.subprocesses = {}

        # Set up basic methods for both communicators
        for comm in [self.sse_communicator, self.stdio_communicator]:
            comm.start = mock.AsyncMock()
            comm.stop = mock.AsyncMock()
            comm.send_request = mock.AsyncMock(return_value={"result": "default"})
            comm.call_tool = mock.AsyncMock(return_value={"result": "default"})
            comm.list_tools = mock.AsyncMock(return_value=[])
            comm._connect_to_service = mock.AsyncMock()

        # Set the primary communicator to SSE for this agent
        self.set_communicator(self.sse_communicator)

    def set_communicator(self, communicator):
        """Set the primary communicator for this agent."""
        self.communicator = communicator

    async def register_service(self, service_name, service_url, communicator_type="sse"):
        """Register a service with the appropriate communicator.

        Args:
            service_name: Name to identify the service
            service_url: URL to connect to the service
            communicator_type: Type of communicator to use ("sse" or "stdio")
        """
        if communicator_type.lower() == "sse":
            self.sse_communicator.service_urls[service_name] = service_url
        elif communicator_type.lower() == "stdio":
            self.stdio_communicator.service_urls[service_name] = service_url
        else:
            raise ValueError(f"Unknown communicator type: {communicator_type}")

    async def _get_communicator_for_service(self, service_name):
        """Get the appropriate communicator for the given service.

        Args:
            service_name: Name of the service

        Returns:
            The communicator that manages this service

        Raises:
            ServiceNotFoundError: If the service is not registered with any communicator
        """
        if service_name in self.sse_communicator.service_urls:
            return self.sse_communicator
        elif service_name in self.stdio_communicator.service_urls:
            return self.stdio_communicator
        else:
            raise ServiceNotFoundError(f"Service '{service_name}' not found", target=service_name)

    async def call_unified_tool(self, service_name, tool_name, arguments=None):
        """Call a tool on any service regardless of communicator type.

        Args:
            service_name: Name of the service to call
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            The result of the tool call
        """
        communicator = await self._get_communicator_for_service(service_name)
        return await communicator.call_tool(target_service=service_name, tool_name=tool_name, arguments=arguments)


@pytest.fixture
def unified_agent():
    """Create a test unified communication agent with mocked communicators."""
    agent = UnifiedCommunicationAgent()
    agent.setup_communicators()
    return agent


class TestUnifiedCommunication:
    """Test unified communication between different MCP communicator types."""

    @pytest.mark.asyncio
    async def test_sse_stdio_registration(self, unified_agent):
        """Test registering services with different communicator types."""
        # Register an SSE and STDIO service
        await unified_agent.register_service("sse_service", "http://localhost:8765/mcp", "sse")
        await unified_agent.register_service("stdio_service", "python -m script.py", "stdio")

        # Verify services are registered with correct communicators
        assert "sse_service" in unified_agent.sse_communicator.service_urls
        assert "stdio_service" in unified_agent.stdio_communicator.service_urls
        assert "sse_service" not in unified_agent.stdio_communicator.service_urls
        assert "stdio_service" not in unified_agent.sse_communicator.service_urls

    @pytest.mark.asyncio
    async def test_service_not_found(self, unified_agent):
        """Test error handling when a service is not found."""
        with pytest.raises(ServiceNotFoundError) as excinfo:
            await unified_agent.call_unified_tool(
                service_name="nonexistent_service", tool_name="test_tool", arguments={"arg": "value"}
            )

        assert "nonexistent_service" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_call_sse_tool(self, unified_agent):
        """Test calling a tool on an SSE service."""
        # Register an SSE service
        await unified_agent.register_service("sse_service", "http://localhost:8765/mcp", "sse")

        # Set up mock responses for the SSE communicator
        unified_agent.sse_communicator.call_tool.return_value = {"result": "sse_result"}

        # Call a tool on the SSE service
        result = await unified_agent.call_unified_tool(
            service_name="sse_service", tool_name="test_tool", arguments={"arg": "value"}
        )

        # Verify the result and that the correct communicator was used
        assert result == {"result": "sse_result"}
        unified_agent.sse_communicator.call_tool.assert_called_once_with(
            target_service="sse_service", tool_name="test_tool", arguments={"arg": "value"}
        )
        unified_agent.stdio_communicator.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_call_stdio_tool(self, unified_agent):
        """Test calling a tool on a STDIO service."""
        # Register a STDIO service
        await unified_agent.register_service("stdio_service", "python -m script.py", "stdio")

        # Set up mock responses for the STDIO communicator
        unified_agent.stdio_communicator.call_tool.return_value = {"result": "stdio_result"}

        # Call a tool on the STDIO service
        result = await unified_agent.call_unified_tool(
            service_name="stdio_service", tool_name="test_tool", arguments={"arg": "value"}
        )

        # Verify the result and that the correct communicator was used
        assert result == {"result": "stdio_result"}
        unified_agent.stdio_communicator.call_tool.assert_called_once_with(
            target_service="stdio_service", tool_name="test_tool", arguments={"arg": "value"}
        )
        unified_agent.sse_communicator.call_tool.assert_not_called()

    @pytest.mark.asyncio
    async def test_unified_communication_setup_teardown(self, unified_agent):
        """Test starting and stopping multiple communicators."""
        # Start the communicators
        await unified_agent.sse_communicator.start()
        await unified_agent.stdio_communicator.start()

        # Register services
        await unified_agent.register_service("sse_service", "http://localhost:8765/mcp", "sse")
        await unified_agent.register_service("stdio_service", "python -m script.py", "stdio")

        # Stop the communicators
        await unified_agent.sse_communicator.stop()
        await unified_agent.stdio_communicator.stop()

        # Verify the start and stop methods were called
        unified_agent.sse_communicator.start.assert_called_once()
        unified_agent.stdio_communicator.start.assert_called_once()
        unified_agent.sse_communicator.stop.assert_called_once()
        unified_agent.stdio_communicator.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_service_forwarding(self, unified_agent):
        """Test forwarding requests between multiple services of different types."""
        # Register multiple services
        await unified_agent.register_service("sse_service1", "http://localhost:8765/mcp", "sse")
        await unified_agent.register_service("sse_service2", "http://localhost:8766/mcp", "sse")
        await unified_agent.register_service("stdio_service1", "python -m script1.py", "stdio")
        await unified_agent.register_service("stdio_service2", "python -m script2.py", "stdio")

        # Configure mock responses
        unified_agent.sse_communicator.call_tool.side_effect = lambda target_service, tool_name, arguments: {
            "result": f"sse_{target_service}_{tool_name}",
            "args": arguments,
        }
        unified_agent.stdio_communicator.call_tool.side_effect = lambda target_service, tool_name, arguments: {
            "result": f"stdio_{target_service}_{tool_name}",
            "args": arguments,
        }

        # Call tools on different services
        sse_result1 = await unified_agent.call_unified_tool(
            service_name="sse_service1", tool_name="tool1", arguments={"arg": "value1"}
        )
        stdio_result1 = await unified_agent.call_unified_tool(
            service_name="stdio_service1", tool_name="tool2", arguments={"arg": "value2"}
        )
        sse_result2 = await unified_agent.call_unified_tool(
            service_name="sse_service2", tool_name="tool3", arguments={"arg": "value3"}
        )
        stdio_result2 = await unified_agent.call_unified_tool(
            service_name="stdio_service2", tool_name="tool4", arguments={"arg": "value4"}
        )

        # Verify results
        assert sse_result1["result"] == "sse_sse_service1_tool1"
        assert sse_result1["args"] == {"arg": "value1"}
        assert stdio_result1["result"] == "stdio_stdio_service1_tool2"
        assert stdio_result1["args"] == {"arg": "value2"}
        assert sse_result2["result"] == "sse_sse_service2_tool3"
        assert sse_result2["args"] == {"arg": "value3"}
        assert stdio_result2["result"] == "stdio_stdio_service2_tool4"
        assert stdio_result2["args"] == {"arg": "value4"}

    @pytest.mark.asyncio
    async def test_error_handling_and_propagation(self, unified_agent):
        """Test that errors are properly propagated from the communicators."""
        # Register services
        await unified_agent.register_service("sse_service", "http://localhost:8765/mcp", "sse")
        await unified_agent.register_service("stdio_service", "python -m script.py", "stdio")

        # Configure the SSE communicator to raise an error
        unified_agent.sse_communicator.call_tool.side_effect = CommunicationError(
            "SSE communication error", target="sse_service"
        )

        # Configure the STDIO communicator to raise a different error
        unified_agent.stdio_communicator.call_tool.side_effect = ValueError("Invalid arguments for STDIO tool")

        # Test SSE error propagation
        with pytest.raises(CommunicationError) as sse_excinfo:
            await unified_agent.call_unified_tool(
                service_name="sse_service", tool_name="test_tool", arguments={"arg": "value"}
            )

        assert "SSE communication error" in str(sse_excinfo.value)
        assert sse_excinfo.value.target == "sse_service"

        # Test STDIO error propagation
        with pytest.raises(ValueError) as stdio_excinfo:
            await unified_agent.call_unified_tool(
                service_name="stdio_service", tool_name="test_tool", arguments={"arg": "value"}
            )

        assert "Invalid arguments for STDIO tool" in str(stdio_excinfo.value)
