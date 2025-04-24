"""Tests for MCP agent and decorators."""

import asyncio
from unittest import mock
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from simple_mas.agent import McpAgent, mcp_prompt, mcp_resource, mcp_tool
from simple_mas.agent.mcp import MCP_PROMPT_ATTR, MCP_RESOURCE_ATTR, MCP_TOOL_ATTR
from simple_mas.config import AgentConfig


class TodoItem(BaseModel):
    """Sample model for testing."""

    id: int
    text: str
    completed: bool = False


class MockMcpCommunicator:
    """Mock MCP communicator for testing."""

    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.server_mode = True
        self.mcp_server = mock.MagicMock()
        self.started = False
        self.stopped = False
        self.agent = None  # Reference to the agent when set_communicator is called

    async def start(self):
        """Start the communicator."""
        self.started = True

        # Register tools, prompts, and resources from the agent if available
        if hasattr(self, "agent") and self.agent is not None:
            # Register tools
            for tool_name, tool_data in self.agent._tools.items():
                metadata = tool_data["metadata"]
                function = tool_data["function"]
                self.mcp_server.add_tool(
                    function,
                    name=metadata.get("name"),
                    description=metadata.get("description"),
                )

            # Register prompts
            for prompt_name, prompt_data in self.agent._prompts.items():
                metadata = prompt_data["metadata"]
                function = prompt_data["function"]
                self.mcp_server.add_prompt(
                    function,
                    name=metadata.get("name"),
                    description=metadata.get("description"),
                )

            # Register resources
            for resource_uri, resource_data in self.agent._resources.items():
                metadata = resource_data["metadata"]
                function = resource_data["function"]
                self.mcp_server.add_resource(
                    function,
                    uri=metadata.get("uri"),
                    name=metadata.get("name"),
                    description=metadata.get("description"),
                    mime_type=metadata.get("mime_type"),
                )

    async def stop(self):
        """Stop the communicator."""
        self.stopped = True


class TestMcpAgent:
    """Tests for the McpAgent class."""

    def test_initialization(self):
        """Test that the agent initializes correctly."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)
        assert agent.name == "test_agent"
        assert agent._tools == {}
        assert agent._prompts == {}
        assert agent._resources == {}
        assert agent._server_mode is False

    def test_decorators_discovery(self):
        """Test that the agent discovers decorated methods."""

        class TestAgent(McpAgent):
            """Test agent with decorated methods."""

            @mcp_tool(description="Test tool")
            async def test_tool(self, param: str) -> dict:
                """Test tool docstring."""
                return {"result": param}

            @mcp_prompt(description="Test prompt")
            async def test_prompt(self, context: str) -> str:
                """Test prompt docstring."""
                return f"Prompt with {context}"

            @mcp_resource(uri="/test", description="Test resource")
            async def test_resource(self) -> bytes:
                """Test resource docstring."""
                return b"Test resource content"

        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = TestAgent(config=config)

        # Check that the tools were discovered
        assert "test_tool" in agent._tools
        assert agent._tools["test_tool"]["metadata"]["description"] == "Test tool"

        # Check that the prompts were discovered
        assert "test_prompt" in agent._prompts
        assert agent._prompts["test_prompt"]["metadata"]["description"] == "Test prompt"

        # Check that the resources were discovered
        assert "/test" in agent._resources
        assert agent._resources["/test"]["metadata"]["description"] == "Test resource"

    @pytest.mark.asyncio
    async def test_server_mode_registration(self):
        """Test that the agent registers methods with the server."""
        # Skip if MCP is not installed, mock HAS_MCP for this test
        with mock.patch("simple_mas.agent.mcp.HAS_MCP", True):

            class TestAgent(McpAgent):
                """Test agent with decorated methods."""

                @mcp_tool(description="Test tool")
                async def test_tool(self, param: str) -> dict:
                    """Test tool docstring."""
                    return {"result": param}

                @mcp_prompt(description="Test prompt")
                async def test_prompt(self, context: str) -> str:
                    """Test prompt docstring."""
                    return f"Prompt with {context}"

                @mcp_resource(uri="/test", description="Test resource")
                async def test_resource(self) -> bytes:
                    """Test resource docstring."""
                    return b"Test resource content"

            config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
            agent = TestAgent(config=config)

            # Create a mock communicator
            communicator = MockMcpCommunicator(agent_name="test_agent")

            # Manually set the agent reference (this happens in the real set_communicator method)
            communicator.agent = agent

            # Set the communicator for the agent
            agent.set_communicator(communicator)

            # Start the agent to trigger registration
            await agent.setup()

            # Now we need to start the communicator to trigger registration
            await communicator.start()

            # Check that the methods were registered with the server
            communicator.mcp_server.add_tool.assert_called()
            communicator.mcp_server.add_prompt.assert_called()
            communicator.mcp_server.add_resource.assert_called()

    @pytest.mark.asyncio
    async def test_lifecycle(self):
        """Test the agent lifecycle."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator
        communicator = MockMcpCommunicator(agent_name="test_agent")
        agent.set_communicator(communicator)

        # Start the agent
        await agent.start()
        assert communicator.started is True

        # Mock the run method to return immediately
        with mock.patch.object(agent, "run", return_value=asyncio.Future()):
            agent._is_running = True
            agent._task = asyncio.Future()
            agent._task.set_result(None)

            # Stop the agent
            await agent.stop()
            assert communicator.stopped is True

    @pytest.mark.asyncio
    async def test_sample_prompt(self):
        """Test the sample_prompt method."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator with sample_prompt method
        communicator = mock.MagicMock()
        sample_prompt_result = {"content": "Sample response"}
        communicator.sample_prompt = AsyncMock(return_value=sample_prompt_result)
        agent.set_communicator(communicator)

        # Call sample_prompt
        messages = [{"role": "user", "content": "Hello"}]
        result = await agent.sample_prompt(
            target_service="test_service",
            messages=messages,
            system_prompt="You are a helpful assistant",
            temperature=0.7,
            max_tokens=100,
        )

        # Check that the communicator's sample_prompt was called with correct args
        communicator.sample_prompt.assert_called_once_with(
            target_service="test_service",
            messages=messages,
            system_prompt="You are a helpful assistant",
            temperature=0.7,
            max_tokens=100,
            include_context=None,
            model_preferences=None,
            stop_sequences=None,
            timeout=None,
        )
        assert result == sample_prompt_result

    @pytest.mark.asyncio
    async def test_sample_prompt_no_support(self):
        """Test sample_prompt with a communicator that doesn't support it."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator without sample_prompt method
        communicator = mock.MagicMock(spec=[])
        agent.set_communicator(communicator)

        # Call sample_prompt should raise an AttributeError
        messages = [{"role": "user", "content": "Hello"}]
        with pytest.raises(AttributeError):
            await agent.sample_prompt(target_service="test_service", messages=messages)

    @pytest.mark.asyncio
    async def test_call_tool(self):
        """Test the call_tool method."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator with call_tool method
        communicator = mock.MagicMock()
        call_tool_result = {"result": "Tool executed successfully"}
        communicator.call_tool = AsyncMock(return_value=call_tool_result)
        agent.set_communicator(communicator)

        # Call call_tool
        arguments = {"param1": "value1", "param2": 42}
        result = await agent.call_tool(
            target_service="test_service", tool_name="test_tool", arguments=arguments, timeout=10.0
        )

        # Check that the communicator's call_tool was called with correct args
        communicator.call_tool.assert_called_once_with(
            target_service="test_service", tool_name="test_tool", arguments=arguments, timeout=10.0
        )
        assert result == call_tool_result

    @pytest.mark.asyncio
    async def test_call_tool_no_support(self):
        """Test call_tool with a communicator that doesn't support it."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator without call_tool method
        communicator = mock.MagicMock(spec=[])
        agent.set_communicator(communicator)

        # Call call_tool should raise an AttributeError
        with pytest.raises(AttributeError):
            await agent.call_tool(target_service="test_service", tool_name="test_tool")

    @pytest.mark.asyncio
    async def test_get_prompt(self):
        """Test the get_prompt method."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator with get_prompt method
        communicator = mock.MagicMock()
        get_prompt_result = "This is a rendered prompt template"
        communicator.get_prompt = AsyncMock(return_value=get_prompt_result)
        agent.set_communicator(communicator)

        # Call get_prompt
        arguments = {"variable": "test"}
        result = await agent.get_prompt(
            target_service="test_service", prompt_name="test_prompt", arguments=arguments, timeout=5.0
        )

        # Check that the communicator's get_prompt was called with correct args
        communicator.get_prompt.assert_called_once_with(
            target_service="test_service", prompt_name="test_prompt", arguments=arguments, timeout=5.0
        )
        assert result == get_prompt_result

    @pytest.mark.asyncio
    async def test_get_prompt_no_support(self):
        """Test get_prompt with a communicator that doesn't support it."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator without get_prompt method
        communicator = mock.MagicMock(spec=[])
        agent.set_communicator(communicator)

        # Call get_prompt should raise an AttributeError
        with pytest.raises(AttributeError):
            await agent.get_prompt(target_service="test_service", prompt_name="test_prompt")

    @pytest.mark.asyncio
    async def test_read_resource(self):
        """Test the read_resource method."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator with read_resource method
        communicator = mock.MagicMock()
        resource_content = b"Test resource content"
        communicator.read_resource = AsyncMock(return_value=resource_content)
        agent.set_communicator(communicator)

        # Call read_resource
        result = await agent.read_resource(target_service="test_service", resource_uri="/test/resource", timeout=3.0)

        # Check that the communicator's read_resource was called with correct args
        communicator.read_resource.assert_called_once_with(
            target_service="test_service", resource_uri="/test/resource", timeout=3.0
        )
        assert result == resource_content

    @pytest.mark.asyncio
    async def test_read_resource_no_support(self):
        """Test read_resource with a communicator that doesn't support it."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator without read_resource method
        communicator = mock.MagicMock(spec=[])
        agent.set_communicator(communicator)

        # Call read_resource should raise an AttributeError
        with pytest.raises(AttributeError):
            await agent.read_resource(target_service="test_service", resource_uri="/test/resource")

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test the list_tools method."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator with list_tools method
        communicator = mock.MagicMock()
        tools_list = [{"name": "tool1", "description": "First tool"}, {"name": "tool2", "description": "Second tool"}]
        communicator.list_tools = AsyncMock(return_value=tools_list)
        agent.set_communicator(communicator)

        # Call list_tools
        result = await agent.list_tools(target_service="test_service")

        # Check that the communicator's list_tools was called with correct args
        communicator.list_tools.assert_called_once_with(target_service="test_service")
        assert result == tools_list

    @pytest.mark.asyncio
    async def test_list_tools_no_support(self):
        """Test list_tools with a communicator that doesn't support it."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator without list_tools method
        communicator = mock.MagicMock(spec=[])
        agent.set_communicator(communicator)

        # Call list_tools should raise an AttributeError
        with pytest.raises(AttributeError):
            await agent.list_tools(target_service="test_service")


class TestMcpDecorators:
    """Tests for the MCP decorators."""

    def test_mcp_tool_decorator(self):
        """Test the mcp_tool decorator."""

        @mcp_tool(name="custom_name", description="Custom description")
        async def test_function(param: str) -> dict:
            """Test function docstring."""
            return {"result": param}

        # Check that the metadata was added to the function
        assert hasattr(test_function, MCP_TOOL_ATTR)
        metadata = getattr(test_function, MCP_TOOL_ATTR)
        assert metadata["name"] == "custom_name"
        assert metadata["description"] == "Custom description"

        # Test with output model
        @mcp_tool(output_model=TodoItem)
        async def test_function_with_model(id: int, text: str) -> dict:
            """Test function with model."""
            return {"id": id, "text": text}

        metadata = getattr(test_function_with_model, MCP_TOOL_ATTR)
        assert metadata["output_model"] == TodoItem

    def test_mcp_prompt_decorator(self):
        """Test the mcp_prompt decorator."""

        @mcp_prompt(name="custom_prompt", description="Custom prompt description")
        async def test_prompt(context: str) -> str:
            """Test prompt docstring."""
            return f"Prompt with {context}"

        # Check that the metadata was added to the function
        assert hasattr(test_prompt, MCP_PROMPT_ATTR)
        metadata = getattr(test_prompt, MCP_PROMPT_ATTR)
        assert metadata["name"] == "custom_prompt"
        assert metadata["description"] == "Custom prompt description"

        # Test with template
        @mcp_prompt(template="This is a template with {{ variable }}")
        async def test_prompt_with_template(variable: str) -> str:
            """Test prompt with template."""
            return f"This is a template with {variable}"

        metadata = getattr(test_prompt_with_template, MCP_PROMPT_ATTR)
        assert metadata["template"] == "This is a template with {{ variable }}"

    def test_mcp_resource_decorator(self):
        """Test the mcp_resource decorator."""

        @mcp_resource(
            uri="/custom/path",
            name="custom_resource",
            description="Custom resource description",
            mime_type="application/json",
        )
        async def test_resource() -> bytes:
            """Test resource docstring."""
            return b'{"result": "value"}'

        # Check that the metadata was added to the function
        assert hasattr(test_resource, MCP_RESOURCE_ATTR)
        metadata = getattr(test_resource, MCP_RESOURCE_ATTR)
        assert metadata["uri"] == "/custom/path"
        assert metadata["name"] == "custom_resource"
        assert metadata["description"] == "Custom resource description"
        assert metadata["mime_type"] == "application/json"
