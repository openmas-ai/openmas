"""Integration tests for McpAgent using AgentTestHarness."""

from typing import Any, Dict, List, Optional, cast

import pytest
from pydantic import BaseModel

from openmas.agent import McpAgent, mcp_prompt, mcp_resource, mcp_tool
from openmas.testing.harness import AgentTestHarness


class TestInputModel(BaseModel):
    """Test input model for tools."""

    param1: str
    param2: int


class TestOutputModel(BaseModel):
    """Test output model for tools."""

    result: str
    code: int


class MockMcpCommunicator:
    """Mock MCP communicator for testing."""

    def __init__(self, agent_name: str, server_mode: bool = False):
        """Initialize the mock communicator.

        Args:
            agent_name: Name of the agent
            server_mode: Whether to run in server mode
        """
        self.agent_name = agent_name
        self.server_mode = server_mode
        self.started = False
        self.stopped = False
        self.agent = None
        self.registered_tools: Dict[str, Dict[str, Any]] = {}
        self.registered_prompts: Dict[str, Dict[str, Any]] = {}
        self.registered_resources: Dict[str, Dict[str, Any]] = {}

        # Client mode mocked responses
        self.mocked_tools = {"remote_tool": {"description": "A remote tool", "parameters": {}}}
        self.mocked_tool_responses: Dict[str, Any] = {}
        self.mocked_prompt_responses: Dict[str, str] = {}
        self.mocked_resource_responses: Dict[str, bytes] = {}

    async def start(self) -> None:
        """Start the communicator."""
        self.started = True

        # If in server mode and agent is set, register decorated methods
        if self.server_mode and self.agent is not None:
            for tool_name, tool_data in self.agent._tools.items():
                await self.register_tool(
                    name=tool_data["metadata"].get("name", tool_name),
                    description=tool_data["metadata"].get("description", ""),
                    function=tool_data["function"],
                )

            for prompt_name, prompt_data in self.agent._prompts.items():
                await self.register_prompt(
                    name=prompt_data["metadata"].get("name", prompt_name),
                    description=prompt_data["metadata"].get("description", ""),
                    function=prompt_data["function"],
                )

            for resource_uri, resource_data in self.agent._resources.items():
                await self.register_resource(
                    name=resource_data["metadata"].get("name", ""),
                    description=resource_data["metadata"].get("description", ""),
                    function=resource_data["function"],
                    mime_type=resource_data["metadata"].get("mime_type", "text/plain"),
                )

    async def stop(self) -> None:
        """Stop the communicator."""
        self.stopped = True

    async def register_tool(self, name: str, description: str, function: Any) -> None:
        """Register a tool with the communicator.

        Args:
            name: The tool name
            description: The tool description
            function: The tool function
        """
        self.registered_tools[name] = {
            "description": description,
            "function": function,
        }

    async def register_prompt(self, name: str, description: str, function: Any) -> None:
        """Register a prompt with the communicator.

        Args:
            name: The prompt name
            description: The prompt description
            function: The prompt function
        """
        self.registered_prompts[name] = {
            "description": description,
            "function": function,
        }

    async def register_resource(
        self, name: str, description: str, function: Any, mime_type: str = "text/plain"
    ) -> None:
        """Register a resource with the communicator.

        Args:
            name: The resource name
            description: The resource description
            function: The resource function
            mime_type: The resource MIME type
        """
        self.registered_resources[name] = {
            "description": description,
            "function": function,
            "mime_type": mime_type,
        }

    # Client mode methods
    async def list_tools(self, target_service: str) -> List[Dict[str, Any]]:
        """List tools available on a service.

        Args:
            target_service: The target service name

        Returns:
            List of tool information dictionaries
        """
        return [{"name": k, **v} for k, v in self.mocked_tools.items()]

    async def call_tool(
        self,
        target_service: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Call a tool on a remote service.

        Args:
            target_service: The target service name
            tool_name: The tool name
            arguments: The tool arguments
            timeout: Optional timeout

        Returns:
            The tool result
        """
        if tool_name in self.mocked_tool_responses:
            return self.mocked_tool_responses[tool_name]
        return {"result": f"Mocked result for {tool_name}", "code": 200}

    async def get_prompt(
        self,
        target_service: str,
        prompt_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> str:
        """Get a prompt from a remote service.

        Args:
            target_service: The target service name
            prompt_name: The prompt name
            arguments: The prompt arguments
            timeout: Optional timeout

        Returns:
            The rendered prompt
        """
        if prompt_name in self.mocked_prompt_responses:
            return self.mocked_prompt_responses[prompt_name]
        return f"Mocked prompt for {prompt_name}"

    async def read_resource(
        self,
        target_service: str,
        resource_uri: str,
        timeout: Optional[float] = None,
    ) -> bytes:
        """Read a resource from a remote service.

        Args:
            target_service: The target service name
            resource_uri: The resource URI
            timeout: Optional timeout

        Returns:
            The resource content
        """
        if resource_uri in self.mocked_resource_responses:
            return self.mocked_resource_responses[resource_uri]
        return f"Mocked resource at {resource_uri}".encode("utf-8")

    async def sample_prompt(
        self,
        target_service: str,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[float] = None,
        include_context: Optional[str] = None,
        model_preferences: Optional[Dict[str, Any]] = None,
        stop_sequences: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Sample a prompt from a service.

        Args:
            target_service: The target service
            messages: The messages to include
            system_prompt: Optional system prompt
            temperature: Optional temperature
            max_tokens: Optional max tokens
            include_context: Optional context inclusion mode
            model_preferences: Optional model preferences
            stop_sequences: Optional stop sequences
            timeout: Optional timeout

        Returns:
            The sampling result
        """
        return {"content": "Mocked sampling response"}

    async def prepare_registration(
        self, tools: Dict[str, Dict[str, Any]], prompts: Dict[str, Dict[str, Any]], resources: Dict[str, Dict[str, Any]]
    ) -> None:
        """Prepare for registration of tools, prompts, and resources.

        Args:
            tools: Dictionary of tools to register
            prompts: Dictionary of prompts to register
            resources: Dictionary of resources to register
        """
        # This method is called during McpAgent.setup() if it exists
        # We can use it to verify that the agent is passing the correct data
        self.tools_to_register = tools
        self.prompts_to_register = prompts
        self.resources_to_register = resources


class TestAgent(McpAgent):
    """Test agent with decorated methods."""

    @mcp_tool(
        name="test_tool",
        description="A test tool",
        input_model=TestInputModel,
        output_model=TestOutputModel,
    )
    async def test_tool(self, param1: str, param2: int) -> Dict[str, Any]:
        """Execute a test tool.

        Args:
            param1: First parameter
            param2: Second parameter

        Returns:
            Tool execution result
        """
        return cast(Dict[str, Any], {"result": f"Processed {param1} and {param2}", "code": 200})

    @mcp_prompt(
        name="test_prompt",
        description="A test prompt",
        template="This is a template with {{ variable }}",
    )
    async def test_prompt(self, variable: str) -> str:
        """Generate a test prompt.

        Args:
            variable: A variable to include in the prompt

        Returns:
            Rendered prompt
        """
        return f"This is a template with {variable}"

    @mcp_resource(
        uri="/test/resource",
        name="test_resource",
        description="A test resource",
        mime_type="application/json",
    )
    async def test_resource(self) -> bytes:
        """Provide a test resource.

        Returns:
            Resource content
        """
        return b'{"key": "value"}'

    # Method to test client delegation
    async def call_remote_tool(self, service_name: str) -> Dict[str, Any]:
        """Call a tool on a remote service.

        Args:
            service_name: The remote service name

        Returns:
            Tool execution result
        """
        result = await self.call_tool(
            target_service=service_name,
            tool_name="remote_tool",
            arguments={"param1": "test", "param2": 42},
        )
        return cast(Dict[str, Any], result)


@pytest.fixture
def mock_communicator_class():
    """Fixture to provide the mock communicator class."""
    return MockMcpCommunicator


class TestMcpAgentIntegration:
    """Integration tests for McpAgent."""

    @pytest.mark.asyncio
    async def test_server_mode_registration(self, mock_communicator_class):
        """Test registration of decorated methods in server mode."""
        # Create a test harness for the TestAgent
        harness = AgentTestHarness(TestAgent)

        # Create an agent
        agent = await harness.create_agent(name="test-agent")

        # Replace the mock communicator with our custom one
        communicator = mock_communicator_class(agent_name=agent.name, server_mode=True)
        agent.set_communicator(communicator)

        # Start the agent
        async with harness.running_agent(agent):
            # Verify that the tools were registered
            assert "test_tool" in communicator.registered_tools
            assert communicator.registered_tools["test_tool"]["description"] == "A test tool"

            # Verify that the prompts were registered
            assert "test_prompt" in communicator.registered_prompts
            assert communicator.registered_prompts["test_prompt"]["description"] == "A test prompt"

            # Verify that the resources were registered
            assert "test_resource" in communicator.registered_resources
            assert communicator.registered_resources["test_resource"]["mime_type"] == "application/json"

            # Verify prepare_registration was called with correct data
            assert len(communicator.tools_to_register) == 1
            assert "test_tool" in communicator.tools_to_register
            assert len(communicator.prompts_to_register) == 1
            assert "test_prompt" in communicator.prompts_to_register
            assert len(communicator.resources_to_register) == 1
            assert "/test/resource" in communicator.resources_to_register

    @pytest.mark.asyncio
    async def test_client_mode_delegation(self, mock_communicator_class):
        """Test delegation to communicator methods in client mode."""
        # Create a test harness for the TestAgent
        harness = AgentTestHarness(TestAgent)

        # Create an agent
        agent = await harness.create_agent(name="test-agent")

        # Replace the mock communicator with our custom one - client mode
        communicator = mock_communicator_class(agent_name=agent.name, server_mode=False)

        # Set up a mock response for the remote_tool
        communicator.mocked_tool_responses["remote_tool"] = {
            "result": "Remote tool executed",
            "code": 200,
        }

        # Set the communicator
        agent.set_communicator(communicator)

        # Start the agent
        async with harness.running_agent(agent):
            # Test call_tool delegation
            result = await agent.call_tool(
                target_service="remote-service",
                tool_name="remote_tool",
                arguments={"param1": "test", "param2": 42},
            )
            assert result["result"] == "Remote tool executed"

            # Test get_prompt delegation
            prompt_result = await agent.get_prompt(
                target_service="remote-service",
                prompt_name="some_prompt",
                arguments={"variable": "test"},
            )
            assert "Mocked prompt" in prompt_result

            # Test read_resource delegation
            resource_result = await agent.read_resource(
                target_service="remote-service",
                resource_uri="/some/resource",
            )
            assert b"Mocked resource at /some/resource" == resource_result

            # Test integrated method that uses delegation
            integrated_result = await agent.call_remote_tool("remote-service")
            assert integrated_result["result"] == "Remote tool executed"

            # Test list_tools delegation
            tools = await agent.list_tools(target_service="remote-service")
            assert len(tools) == 1
            assert tools[0]["name"] == "remote_tool"

    @pytest.mark.asyncio
    async def test_model_validation(self, mock_communicator_class):
        """Test that Pydantic models from decorators are used correctly."""
        # Create a test harness for the TestAgent
        harness = AgentTestHarness(TestAgent)

        # Create an agent
        agent = await harness.create_agent(name="test-agent")

        # Check that the models were correctly stored in metadata
        tool_data = agent._tools["test_tool"]
        metadata = tool_data["metadata"]

        # Verify input model
        assert metadata["input_model"] == TestInputModel

        # Verify output model
        assert metadata["output_model"] == TestOutputModel

        # Verify that prompt template was stored
        prompt_data = agent._prompts["test_prompt"]
        prompt_metadata = prompt_data["metadata"]
        assert prompt_metadata["template"] == "This is a template with {{ variable }}"
