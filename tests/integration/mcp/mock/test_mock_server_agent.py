"""Integration tests for MCP Server Agent interaction with MCP Communicator using mocks.

This module tests the integration between McpServerAgent and McpSseCommunicator
in server mode, verifying that decorated methods are properly registered.
This file uses mock implementations without real dependencies.
"""

from typing import Any, Dict

import pytest
from pydantic import BaseModel

from openmas.agent import McpServerAgent
from openmas.agent.mcp import mcp_prompt, mcp_resource, mcp_tool
from openmas.testing.harness import AgentTestHarness


class InputModel(BaseModel):
    """Test input model for MCP tool."""

    name: str
    value: int


class OutputModel(BaseModel):
    """Test output model for MCP tool."""

    result: str
    status: int


class MockMcpSseCommunicator:
    """Mock MCP SSE communicator for testing server mode registration."""

    def __init__(self, agent_name: str, service_urls: Dict[str, str], server_mode: bool = True, **kwargs):
        """Initialize the mock communicator.

        Args:
            agent_name: Agent name
            service_urls: Service URLs
            server_mode: Server mode flag
            **kwargs: Additional arguments
        """
        self.agent_name = agent_name
        self.service_urls = service_urls
        self.server_mode = server_mode
        self.agent = None
        self.registered_tools: Dict[str, Dict[str, Any]] = {}
        self.registered_prompts: Dict[str, Dict[str, Any]] = {}
        self.registered_resources: Dict[str, Dict[str, Any]] = {}
        self.tools_to_register: Dict[str, Dict[str, Any]] = {}
        self.prompts_to_register: Dict[str, Dict[str, Any]] = {}
        self.resources_to_register: Dict[str, Dict[str, Any]] = {}

    async def start(self) -> None:
        """Start the communicator."""
        # If we have an agent reference and we're in server mode, auto-register methods
        if hasattr(self, "agent") and self.agent and self.server_mode:
            if hasattr(self.agent, "_tools") and self.agent._tools:
                self.tools_to_register = self.agent._tools
                for name, tool_info in self.agent._tools.items():
                    await self.register_tool(
                        name=name,
                        description=tool_info.get("metadata", {}).get("description", ""),
                        function=tool_info.get("handler"),
                    )

            if hasattr(self.agent, "_prompts") and self.agent._prompts:
                self.prompts_to_register = self.agent._prompts
                for name, prompt_info in self.agent._prompts.items():
                    await self.register_prompt(
                        name=name,
                        description=prompt_info.get("metadata", {}).get("description", ""),
                        function=prompt_info.get("handler"),
                    )

            if hasattr(self.agent, "_resources") and self.agent._resources:
                for uri, resource_info in self.agent._resources.items():
                    self.resources_to_register[uri] = resource_info
                    await self.register_resource(
                        name=resource_info.get("metadata", {}).get("name", ""),
                        description=resource_info.get("metadata", {}).get("description", ""),
                        function=resource_info.get("handler"),
                        mime_type=resource_info.get("metadata", {}).get("mime_type", "text/plain"),
                    )

    async def stop(self) -> None:
        """Stop the communicator."""
        pass

    async def register_tool(self, name: str, description: str, function: Any) -> None:
        """Register a tool.

        Args:
            name: Tool name
            description: Tool description
            function: Tool handler function
        """
        self.registered_tools[name] = {
            "name": name,
            "description": description,
            "function": function,
        }

    async def register_prompt(self, name: str, description: str, function: Any) -> None:
        """Register a prompt.

        Args:
            name: Prompt name
            description: Prompt description
            function: Prompt handler function
        """
        self.registered_prompts[name] = {
            "name": name,
            "description": description,
            "function": function,
        }

    async def register_resource(
        self, name: str, description: str, function: Any, mime_type: str = "text/plain"
    ) -> None:
        """Register a resource.

        Args:
            name: Resource name
            description: Resource description
            function: Resource handler function
            mime_type: Resource MIME type
        """
        self.registered_resources[name] = {
            "name": name,
            "description": description,
            "function": function,
            "mime_type": mime_type,
        }

    async def prepare_registration(
        self, tools: Dict[str, Dict[str, Any]], prompts: Dict[str, Dict[str, Any]], resources: Dict[str, Dict[str, Any]]
    ) -> None:
        """Prepare for registration of tools, prompts, and resources.

        Args:
            tools: Dictionary of tools to register
            prompts: Dictionary of prompts to register
            resources: Dictionary of resources to register
        """
        self.tools_to_register = tools
        self.prompts_to_register = prompts
        self.resources_to_register = resources


@pytest.mark.no_collect
class MockMcpServerAgent(McpServerAgent):
    """Mock MCP server agent."""

    @mcp_tool(name="calculate", description="Calculate a mathematical expression")
    async def calculate(self, expression: str) -> Dict[str, Any]:
        """Calculate a mathematical expression.

        Args:
            expression: The expression to calculate

        Returns:
            The calculation result
        """
        try:
            result = eval(expression, {"__builtins__": {}})
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    @mcp_tool(name="process_input", description="Process input data", input_model=InputModel, output_model=OutputModel)
    async def process_input(self, name: str, value: int) -> Dict[str, Any]:
        """Process input data.

        Args:
            name: The name parameter
            value: The value parameter

        Returns:
            Processing result
        """
        return {"result": f"Processed {name} with value {value}", "status": 200}

    @mcp_prompt(
        name="greeting_template",
        description="Generate a greeting",
        template="Hello, {{ name }}! Welcome to {{ service }}.",
    )
    async def greeting_prompt(self, name: str, service: str) -> str:
        """Generate a greeting.

        Args:
            name: Person's name
            service: Service name

        Returns:
            Greeting message
        """
        return f"Hello, {name}! Welcome to {service}."

    @mcp_resource(uri="/api/data", name="sample_data", description="Sample data resource", mime_type="application/json")
    async def sample_data(self) -> bytes:
        """Provide sample data.

        Returns:
            Sample data as bytes
        """
        return b'{"sample": "data", "version": 1}'


@pytest.mark.mcp
@pytest.mark.mock
class TestMcpServerAgentIntegration:
    """Integration tests for McpServerAgent with communicator."""

    @pytest.mark.asyncio
    async def test_server_agent_tool_registration(self, tmp_path):
        """Test registration of tools in server mode."""
        # Create a test harness
        harness = AgentTestHarness(MockMcpServerAgent, project_root=tmp_path)

        # Create an agent
        agent = await harness.create_agent(name="test-server")

        # Make sure the agent methods are decorated properly
        assert hasattr(agent, "_tools")
        assert "calculate" in agent._tools
        assert "process_input" in agent._tools

        # Replace the mock communicator with our custom one
        communicator = MockMcpSseCommunicator(
            agent_name=agent.name, service_urls={}, server_mode=True, http_port=8765, server_instructions="Test server"
        )

        # Set the communicator
        agent.set_communicator(communicator)

        # Explicitly set agent on communicator (normally done by set_communicator)
        communicator.agent = agent

        # Start the agent
        async with harness.running_agent(agent):
            # Verify that the tools were registered
            assert "calculate" in communicator.registered_tools
            assert communicator.registered_tools["calculate"]["description"] == "Calculate a mathematical expression"

            assert "process_input" in communicator.registered_tools
            assert communicator.registered_tools["process_input"]["description"] == "Process input data"

            # Verify that prepare_registration was called with correct data
            assert len(communicator.tools_to_register) == 2
            assert "calculate" in communicator.tools_to_register
            assert "process_input" in communicator.tools_to_register

    @pytest.mark.asyncio
    async def test_server_agent_prompt_registration(self, tmp_path):
        """Test registration of prompts in server mode."""
        # Create a test harness
        harness = AgentTestHarness(MockMcpServerAgent, project_root=tmp_path)

        # Create an agent
        agent = await harness.create_agent(name="test-server")

        # Make sure the agent methods are decorated properly
        assert hasattr(agent, "_prompts")
        assert "greeting_template" in agent._prompts

        # Replace the mock communicator with our custom one
        communicator = MockMcpSseCommunicator(
            agent_name=agent.name, service_urls={}, server_mode=True, http_port=8765, server_instructions="Test server"
        )

        # Set the communicator
        agent.set_communicator(communicator)

        # Explicitly set agent on communicator (normally done by set_communicator)
        communicator.agent = agent

        # Start the agent
        async with harness.running_agent(agent):
            # Verify that the prompts were registered
            assert "greeting_template" in communicator.registered_prompts
            assert communicator.registered_prompts["greeting_template"]["description"] == "Generate a greeting"

            # Verify that prepare_registration was called with correct data
            assert len(communicator.prompts_to_register) == 1
            assert "greeting_template" in communicator.prompts_to_register

    @pytest.mark.asyncio
    async def test_server_agent_resource_registration(self, tmp_path):
        """Test registration of resources in server mode."""
        # Create a test harness
        harness = AgentTestHarness(MockMcpServerAgent, project_root=tmp_path)

        # Create an agent
        agent = await harness.create_agent(name="test-server")

        # Make sure the agent methods are decorated properly
        assert hasattr(agent, "_resources")
        assert "/api/data" in agent._resources
        assert agent._resources["/api/data"]["metadata"]["name"] == "sample_data"

        # Replace the mock communicator with our custom one
        communicator = MockMcpSseCommunicator(
            agent_name=agent.name, service_urls={}, server_mode=True, http_port=8765, server_instructions="Test server"
        )

        # Set the communicator
        agent.set_communicator(communicator)

        # Explicitly set agent on communicator (normally done by set_communicator)
        communicator.agent = agent

        # Start the agent
        async with harness.running_agent(agent):
            # Verify that the resources were registered
            assert "sample_data" in communicator.registered_resources
            assert communicator.registered_resources["sample_data"]["description"] == "Sample data resource"
            assert communicator.registered_resources["sample_data"]["mime_type"] == "application/json"

            # Verify that prepare_registration was called with correct data
            assert len(communicator.resources_to_register) == 1
            assert "/api/data" in communicator.resources_to_register
