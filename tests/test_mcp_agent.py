"""Tests for the MCP agent implementation."""

import types
from typing import Any, Dict
from unittest import mock

import pytest
from pydantic import BaseModel

# Skip tests if MCP is not available
try:
    import mcp  # noqa: F401

    from simple_mas.agent import McpAgent, mcp_prompt, mcp_resource, mcp_tool
    from simple_mas.communication.mcp import McpSseCommunicator
    from simple_mas.config import AgentConfig

    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    pytest.skip("MCP module is not available", allow_module_level=True)


class InputModel(BaseModel):
    """Test input model."""

    name: str
    value: int = 0


class OutputModel(BaseModel):
    """Test output model."""

    result: str
    code: int


class TestMcpAgent:
    """Tests for the MCP agent implementation."""

    class TestAgent(McpAgent):
        """Test agent with MCP-decorated methods."""

        def __init__(self, name: str) -> None:
            # Create a proper AgentConfig object
            config = AgentConfig(name=name, log_level="INFO", service_urls={})
            super().__init__(config)
            self.setup_called = False
            self.run_called = False
            self.shutdown_called = False

        async def setup(self) -> None:
            """Set up the agent."""
            self.setup_called = True

        async def run(self) -> None:
            """Run the agent."""
            self.run_called = True

        async def shutdown(self) -> None:
            """Shut down the agent."""
            self.shutdown_called = True

        @mcp_tool(description="Test tool")
        async def test_tool(self, name: str, value: int = 0) -> Dict[str, Any]:
            """Test tool method."""
            return {"result": f"Hello, {name}", "code": value}

        @mcp_tool(
            name="custom_name_tool",
            description="Tool with custom name",
            input_model=InputModel,
            output_model=OutputModel,
        )
        async def another_tool(self, name: str, value: int = 0) -> Dict[str, Any]:
            """Another test tool."""
            return {"result": f"Hello, {name}", "code": value}

        @mcp_prompt(description="Test prompt")
        async def test_prompt(self, topic: str) -> str:
            """Test prompt method."""
            return f"Content about {topic}"

        @mcp_resource(
            uri="/test",
            description="Test resource",
            mime_type="text/plain",
        )
        async def test_resource(self) -> bytes:
            """Test resource method."""
            return b"Test resource content"

    @pytest.mark.asyncio
    async def test_mcp_tool_decorator_attributes(self) -> None:
        """Test that the mcp_tool decorator sets the correct attributes."""
        agent = self.TestAgent("test-agent")

        # Check attributes on test_tool
        assert hasattr(agent.test_tool, "_mcp_type")
        assert agent.test_tool._mcp_type == "tool"
        assert agent.test_tool._mcp_description == "Test tool"
        assert hasattr(agent.test_tool, "_mcp_input_model")
        assert not hasattr(agent.test_tool, "_mcp_output_model")

        # Check attributes on another_tool
        assert hasattr(agent.another_tool, "_mcp_type")
        assert agent.another_tool._mcp_type == "tool"
        assert agent.another_tool._mcp_name == "custom_name_tool"
        assert agent.another_tool._mcp_description == "Tool with custom name"
        assert agent.another_tool._mcp_input_model == InputModel
        assert agent.another_tool._mcp_output_model == OutputModel

    @pytest.mark.asyncio
    async def test_mcp_prompt_decorator_attributes(self) -> None:
        """Test that the mcp_prompt decorator sets the correct attributes."""
        agent = self.TestAgent("test-agent")

        assert hasattr(agent.test_prompt, "_mcp_type")
        assert agent.test_prompt._mcp_type == "prompt"
        assert agent.test_prompt._mcp_description == "Test prompt"

    @pytest.mark.asyncio
    async def test_mcp_resource_decorator_attributes(self) -> None:
        """Test that the mcp_resource decorator sets the correct attributes."""
        agent = self.TestAgent("test-agent")

        assert hasattr(agent.test_resource, "_mcp_type")
        assert agent.test_resource._mcp_type == "resource"
        assert agent.test_resource._mcp_description == "Test resource"
        assert agent.test_resource._mcp_uri == "/test"
        assert agent.test_resource._mcp_mime_type == "text/plain"

    @pytest.mark.asyncio
    @mock.patch("simple_mas.agent.mcp.asyncio.sleep")
    async def test_mcp_agent_with_sse_communicator(self, mock_sleep: mock.AsyncMock) -> None:
        """Test MCP agent with SSE communicator in server mode."""
        # Create a mock FastMCP instance
        mock_server = mock.MagicMock()
        mock_add_tool = mock.MagicMock()
        mock_add_prompt = mock.MagicMock()
        mock_add_resource = mock.MagicMock()
        mock_server.add_tool = mock_add_tool
        mock_server.add_prompt = mock_add_prompt
        mock_server.add_resource = mock_add_resource

        # Create a mock SSE communicator with proper async mocks
        mock_communicator = mock.MagicMock(spec=McpSseCommunicator)
        mock_communicator.server_mode = True
        mock_communicator.server = mock_server
        mock_communicator.start = mock.AsyncMock()
        mock_communicator.stop = mock.AsyncMock()
        mock_communicator.register_tool = mock.AsyncMock()
        mock_communicator.register_prompt = mock.AsyncMock()
        mock_communicator.register_resource = mock.AsyncMock()

        # Create the agent
        agent = self.TestAgent("test-agent")
        agent.set_communicator(mock_communicator)

        # Start the agent
        await agent.start()

        # Check that the communicator was started
        mock_communicator.start.assert_called_once()

        # Verify that all the methods were registered
        assert mock_communicator.register_tool.call_count == 2
        mock_communicator.register_tool.assert_any_call(
            name="test_tool", description="Test tool", function=agent.test_tool
        )
        mock_communicator.register_tool.assert_any_call(
            name="custom_name_tool", description="Tool with custom name", function=agent.another_tool
        )

        mock_communicator.register_prompt.assert_called_once_with(
            name="test_prompt", description="Test prompt", function=agent.test_prompt
        )

        mock_communicator.register_resource.assert_called_once_with(
            uri="/test", description="Test resource", function=agent.test_resource, mime_type="text/plain"
        )

        # Verify that setup was called
        assert agent.setup_called

        # Stop the agent
        await agent.stop()

        # Verify that the communicator was stopped
        mock_communicator.stop.assert_called_once()
        assert agent.shutdown_called

    @pytest.mark.asyncio
    async def test_tool_input_validation(self) -> None:
        """Test that input validation works with the Pydantic model."""
        agent = self.TestAgent("test-agent")

        # Valid input
        result = await agent.another_tool(name="test", value=42)
        assert result == {"result": "Hello, test", "code": 42}

        # Invalid input would raise a validation error from Pydantic
        with pytest.raises(Exception):
            await agent.another_tool(invalid_param="test")

    @pytest.mark.asyncio
    async def test_tool_output_validation(self) -> None:
        """Test that output validation works with the Pydantic model."""
        agent = self.TestAgent("test-agent")

        # Call the tool with valid input
        result = await agent.another_tool(name="test", value=42)

        # Check that the output was validated and transformed
        assert isinstance(result, dict)
        assert result["result"] == "Hello, test"
        assert result["code"] == 42

    @pytest.mark.asyncio
    async def test_mcp_register_methods(self) -> None:
        """Test registering MCP methods with the SSE communicator."""
        # Create the agent
        agent = self.TestAgent("test-agent")

        # Create a simple mock with async methods that we can track
        mock_communicator = mock.MagicMock()
        mock_communicator.register_tool = mock.AsyncMock()
        mock_communicator.register_prompt = mock.AsyncMock()
        mock_communicator.register_resource = mock.AsyncMock()

        # Set the communicator
        agent.set_communicator(mock_communicator)

        # Register the methods directly
        await agent._register_mcp_methods()

        # Check that register_tool was called for each tool
        assert mock_communicator.register_tool.call_count == 2
        mock_communicator.register_tool.assert_any_call(
            name="test_tool", description="Test tool", function=agent.test_tool
        )
        mock_communicator.register_tool.assert_any_call(
            name="custom_name_tool", description="Tool with custom name", function=agent.another_tool
        )

        # Check that register_prompt was called
        mock_communicator.register_prompt.assert_called_once_with(
            name="test_prompt", description="Test prompt", function=agent.test_prompt
        )

        # Check that register_resource was called
        mock_communicator.register_resource.assert_called_once_with(
            uri="/test", description="Test resource", function=agent.test_resource, mime_type="text/plain"
        )

        # Reset the mocks for the next test
        mock_communicator.register_tool.reset_mock()
        mock_communicator.register_prompt.reset_mock()
        mock_communicator.register_resource.reset_mock()

        # Test with a new resource
        @mcp_resource(uri="test_resource", description="A test resource")
        async def new_resource(self) -> str:
            return "resource value"

        # Attach the method to the agent
        original_resource = agent.test_resource
        agent.test_resource = types.MethodType(new_resource, agent)

        # Re-register the methods
        agent._discover_mcp_methods()  # Refresh the discovered methods
        await agent._register_mcp_methods()

        # Check that register_resource was called with the new resource
        assert mock_communicator.register_resource.call_count == 2
        mock_communicator.register_resource.assert_any_call(
            uri="test_resource",
            description="A test resource",
            function=agent.test_resource,
            mime_type="application/octet-stream",
        )

        # Restore the original resource
        agent.test_resource = original_resource
