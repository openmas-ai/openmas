"""Tests for MCP agent and decorators."""

import asyncio
from unittest import mock
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from openmas.agent import McpAgent, mcp_prompt, mcp_resource, mcp_tool
from openmas.agent.mcp import MCP_PROMPT_ATTR, MCP_RESOURCE_ATTR, MCP_TOOL_ATTR
from openmas.config import AgentConfig
from tests.unit.communication.mcp.mcp_mocks import apply_mcp_mocks

# Apply MCP mocks
apply_mcp_mocks()


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

        # No need to patch HAS_MCP as we're using the mocking system
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

        # Set up the mock communicator
        communicator = AsyncMock()
        sample_result = {"content": "Sample prompt result"}
        communicator.sample_prompt = AsyncMock(return_value=sample_result)

        # Set the communicator
        agent.set_communicator(communicator)

        # Call the method with proper parameters
        messages = [{"role": "user", "content": "Hello"}]
        result = await agent.sample_prompt(
            target_service="test_service",
            messages=messages,
            system_prompt="You are a helpful assistant",
            temperature=0.7,
            max_tokens=100,
        )

        # Check the result
        assert result == sample_result
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

    @pytest.mark.asyncio
    async def test_sample_prompt_no_support(self):
        """Test the sample_prompt method when the communicator doesn't support it."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Create a mock communicator without MCP protocol support
        communicator = AsyncMock()
        # Patch the isinstance check to return False
        with mock.patch("openmas.agent.mcp.isinstance", return_value=False):
            agent.set_communicator(communicator)

            # Call should raise AttributeError
            with pytest.raises(AttributeError, match="Communicator does not support sample_prompt method"):
                await agent.sample_prompt(
                    target_service="test_service", messages=[{"role": "user", "content": "Hello"}]
                )

    @pytest.mark.asyncio
    async def test_call_tool(self):
        """Test the call_tool method."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Set up the mock communicator
        communicator = AsyncMock()
        tool_result = {"result": "Tool result"}
        communicator.call_tool = AsyncMock(return_value=tool_result)

        # Set the communicator
        agent.set_communicator(communicator)

        # Call the method
        result = await agent.call_tool(
            target_service="service_name", tool_name="test_tool", arguments={"param": "value"}
        )

        # Check the result
        assert result == tool_result
        communicator.call_tool.assert_called_once_with(
            target_service="service_name", tool_name="test_tool", arguments={"param": "value"}, timeout=None
        )

    @pytest.mark.asyncio
    async def test_call_tool_no_support(self):
        """Test the call_tool method when the communicator doesn't support it."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Set up the mock communicator
        communicator = AsyncMock()
        agent.set_communicator(communicator)

        # Patch the hasattr check specifically in the McpAgent.call_tool method
        with mock.patch("openmas.agent.mcp.hasattr", return_value=False):
            # Call the method - should raise AttributeError
            with pytest.raises(AttributeError, match="Communicator does not support call_tool method"):
                await agent.call_tool(
                    target_service="service_name", tool_name="test_tool", arguments={"param": "value"}
                )

    @pytest.mark.asyncio
    async def test_get_prompt(self):
        """Test the get_prompt method."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Set up the mock communicator
        communicator = AsyncMock()
        prompt_result = "Prompt template"
        communicator.get_prompt = AsyncMock(return_value=prompt_result)

        # Set the communicator
        agent.set_communicator(communicator)

        # Call the method
        result = await agent.get_prompt(
            target_service="service_name", prompt_name="test_prompt", arguments={"var": "value"}
        )

        # Check the result
        assert result == prompt_result
        communicator.get_prompt.assert_called_once_with(
            target_service="service_name", prompt_name="test_prompt", arguments={"var": "value"}, timeout=None
        )

    @pytest.mark.asyncio
    async def test_get_prompt_no_support(self):
        """Test the get_prompt method when the communicator doesn't support it."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Set up the mock communicator
        communicator = AsyncMock()
        agent.set_communicator(communicator)

        # Patch the hasattr check specifically in the McpAgent.get_prompt method
        with mock.patch("openmas.agent.mcp.hasattr", return_value=False):
            # Call the method - should raise AttributeError
            with pytest.raises(AttributeError, match="Communicator does not support get_prompt method"):
                await agent.get_prompt(target_service="service_name", prompt_name="test_prompt")

    @pytest.mark.asyncio
    async def test_read_resource(self):
        """Test the read_resource method."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Set up the mock communicator
        communicator = AsyncMock()
        resource_content = b"Resource content"
        communicator.read_resource = AsyncMock(return_value=resource_content)

        # Set the communicator
        agent.set_communicator(communicator)

        # Call the method
        result = await agent.read_resource(target_service="service_name", resource_uri="/test/resource")

        # Check the result
        assert result == resource_content
        communicator.read_resource.assert_called_once_with(
            target_service="service_name", resource_uri="/test/resource", timeout=None
        )

    @pytest.mark.asyncio
    async def test_read_resource_no_support(self):
        """Test the read_resource method when the communicator doesn't support it."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Set up the mock communicator
        communicator = AsyncMock()
        agent.set_communicator(communicator)

        # Patch the hasattr check specifically in the McpAgent.read_resource method
        with mock.patch("openmas.agent.mcp.hasattr", return_value=False):
            # Call the method - should raise AttributeError
            with pytest.raises(AttributeError, match="Communicator does not support read_resource method"):
                await agent.read_resource(target_service="service_name", resource_uri="/test/resource")

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test the list_tools method."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Set up the mock communicator
        communicator = AsyncMock()
        tools = [
            {"name": "tool1", "description": "Tool 1"},
            {"name": "tool2", "description": "Tool 2"},
        ]
        communicator.list_tools = AsyncMock(return_value=tools)

        # Set the communicator
        agent.set_communicator(communicator)

        # Call the method
        result = await agent.list_tools(target_service="service_name")

        # Check the result
        assert result == tools
        communicator.list_tools.assert_called_once_with(target_service="service_name")

    @pytest.mark.asyncio
    async def test_list_tools_no_support(self):
        """Test the list_tools method when the communicator doesn't support it."""
        config = AgentConfig(name="test_agent", log_level="INFO", service_urls={})
        agent = McpAgent(config=config)

        # Set up the mock communicator
        communicator = AsyncMock()
        agent.set_communicator(communicator)

        # Patch the hasattr check specifically in the McpAgent.list_tools method
        with mock.patch("openmas.agent.mcp.hasattr", return_value=False):
            # Call the method - should raise AttributeError
            with pytest.raises(AttributeError, match="Communicator does not support list_tools method"):
                await agent.list_tools(target_service="service_name")


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
