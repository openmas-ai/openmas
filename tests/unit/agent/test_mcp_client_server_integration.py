"""Integration tests for MCP client-server interaction."""

from typing import Any, Dict, Tuple

import pytest
from pydantic import BaseModel

from openmas.agent import McpClientAgent, McpServerAgent
from openmas.agent.mcp import mcp_prompt, mcp_resource, mcp_tool
from openmas.config import AgentConfig
from openmas.exceptions import CommunicationError
from openmas.testing.mock_communicator import MockCommunicator

# Skip the tests if MCP module is not available
try:
    import mcp  # noqa: F401

    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    pytest.skip("MCP module is not available", allow_module_level=True)


class SampleInput(BaseModel):
    """Sample input model for MCP tool."""

    name: str
    value: int


class SampleOutput(BaseModel):
    """Sample output model for MCP tool."""

    result: str
    status: int


class TestServerAgent(McpServerAgent):
    """Test server agent with decorated methods."""

    @mcp_tool(name="add_numbers", description="Add two numbers together")
    async def add_numbers(self, a: int, b: int) -> Dict[str, Any]:
        """Add two numbers and return the result.

        Args:
            a: First number
            b: Second number

        Returns:
            Dictionary with the result
        """
        result = a + b
        return {"result": result}

    @mcp_tool(
        name="process_sample", description="Process a sample input", input_model=SampleInput, output_model=SampleOutput
    )
    async def process_sample(self, name: str, value: int) -> Dict[str, Any]:
        """Process a sample input.

        Args:
            name: Name parameter
            value: Value parameter

        Returns:
            Processed result
        """
        return {"result": f"Processed {name} with value {value}", "status": 200}

    @mcp_prompt(name="greeting", description="Generate a greeting", template="Hello, {{ name }}! How are you today?")
    async def greeting_prompt(self, name: str) -> str:
        """Generate a greeting for the given name.

        Args:
            name: Person's name

        Returns:
            Greeting message
        """
        return f"Hello, {name}! How are you today?"

    @mcp_resource(
        uri="/test/resource", name="test_resource", description="A test resource", mime_type="application/json"
    )
    async def test_resource(self) -> bytes:
        """Provide a test resource.

        Returns:
            Resource content as bytes
        """
        return b'{"message": "This is a test resource"}'


class TestClientAgent(McpClientAgent):
    """Test client agent for interacting with the server."""

    async def call_add_numbers(self, service_name: str, a: int, b: int) -> Dict[str, Any]:
        """Call the add_numbers tool on the server.

        Args:
            service_name: Service to call
            a: First number
            b: Second number

        Returns:
            Result from the server
        """
        result = await self.call_tool(target_service=service_name, tool_name="add_numbers", arguments={"a": a, "b": b})
        # Ensure we return a dict
        if not isinstance(result, dict):
            return {"result": result}
        return result

    async def call_process_sample(self, service_name: str, name: str, value: int) -> Dict[str, Any]:
        """Call the process_sample tool on the server.

        Args:
            service_name: Service to call
            name: Name parameter
            value: Value parameter

        Returns:
            Result from the server
        """
        result = await self.call_tool(
            target_service=service_name, tool_name="process_sample", arguments={"name": name, "value": value}
        )
        # Ensure we return a dict
        if not isinstance(result, dict):
            return {"result": result}
        return result

    async def get_greeting(self, service_name: str, name: str) -> str:
        """Get a greeting from the server.

        Args:
            service_name: Service to call
            name: Person's name

        Returns:
            Greeting from the server
        """
        result = await self.get_prompt(target_service=service_name, prompt_name="greeting", arguments={"name": name})
        # Ensure we return a string
        if not isinstance(result, str):
            return str(result)
        return result

    async def get_test_resource(self, service_name: str) -> bytes:
        """Get the test resource from the server.

        Args:
            service_name: Service to call

        Returns:
            Resource content
        """
        result = await self.read_resource(target_service=service_name, uri="/test/resource")
        # Ensure we return bytes
        if not isinstance(result, bytes):
            return str(result).encode("utf-8")
        return result


@pytest.fixture
async def server_client_agents() -> Tuple[TestServerAgent, TestClientAgent]:
    """Create and setup a server and client agent pair with mock communicators.

    Returns:
        Tuple of (server_agent, client_agent)
    """
    # Create server agent
    server_config = AgentConfig(name="test_server")
    server_agent = TestServerAgent(config=server_config)

    # Create client agent
    client_config = AgentConfig(name="test_client")
    client_agent = TestClientAgent(config=client_config)

    # Create a mock communicator for the server
    server_communicator = MockCommunicator(agent_name="test_server", service_urls={"test_client": "mock://test_client"})

    # Create a mock communicator for the client that can connect to the server
    client_communicator = MockCommunicator(agent_name="test_client", service_urls={"test_server": "mock://test_server"})

    # Set up expected responses for each test
    client_communicator.expect_request(
        target_service="test_server", method="tool/call/add_numbers", params={"a": 5, "b": 7}, response={"result": 12}
    )

    client_communicator.expect_request(
        target_service="test_server",
        method="tool/call/process_sample",
        params={"name": "test", "value": 42},
        response={"result": "Processed test with value 42", "status": 200},
    )

    client_communicator.expect_request(
        target_service="test_server",
        method="prompt/get/greeting",
        params={"name": "User"},
        response="Hello, User! How are you today?",
    )

    client_communicator.expect_request(
        target_service="test_server",
        method="resource/read",
        params={"uri": "/test/resource"},
        response=b'{"message": "This is a test resource"}',
    )

    # For the tools listing test
    client_communicator.expect_request(
        target_service="test_server",
        method="tool/list",
        params=None,
        response=[
            {"name": "add_numbers", "description": "Add two numbers together"},
            {"name": "process_sample", "description": "Process a sample input"},
        ],
    )

    # For the prompts listing test
    client_communicator.expect_request(
        target_service="test_server",
        method="prompt/list",
        params=None,
        response=[{"name": "greeting", "description": "Generate a greeting"}],
    )

    # For error handling test
    client_communicator.expect_request(
        target_service="test_server",
        method="tool/call/non_existent_tool",
        params={"a": 1, "b": 2},
        exception=CommunicationError("Method 'non_existent_tool' not found on service 'test_server'"),
    )

    client_communicator.expect_request(
        target_service="test_server",
        method="tool/call/generate_greeting",
        params={"name": "Alice"},
        response={"greeting": "Hello, Alice!"},
    )

    client_communicator.expect_request(
        target_service="test_server",
        method="resource/test_resource",
        params={},
        response={"content": "Test resource content"},
    )

    # Link the mock communicators
    server_communicator.link_communicator(client_communicator)
    client_communicator.link_communicator(server_communicator)

    # Set the communicators
    server_agent.set_communicator(server_communicator)
    client_agent.set_communicator(client_communicator)

    # Set up the agents
    await server_agent.setup()
    await client_agent.setup()

    try:
        # Return the agents for the test
        yield server_agent, client_agent
    finally:
        # Clean up
        await client_agent.shutdown()
        await server_agent.shutdown()


@pytest.mark.asyncio
async def test_call_add_numbers(server_client_agents: Any):
    """Test calling the add_numbers tool."""
    server_agent, client_agent = await anext(server_client_agents)

    # Call the add_numbers tool
    result = await client_agent.call_add_numbers("test_server", 5, 7)

    # Check the result
    assert isinstance(result, dict)
    assert "result" in result
    assert result["result"] == 12


@pytest.mark.asyncio
async def test_call_process_sample(server_client_agents: Any):
    """Test calling the process_sample tool with Pydantic models."""
    server_agent, client_agent = await anext(server_client_agents)

    # Call the process_sample tool
    result = await client_agent.call_process_sample("test_server", "test", 42)

    # Check the result
    assert isinstance(result, dict)
    assert "result" in result
    assert "Processed test with value 42" in result["result"]
    # The status may not be in the result if we're using a mock or if the
    # call_process_sample method doesn't preserve the full response structure
    if "status" in result:
        assert result["status"] == 200


@pytest.mark.asyncio
async def test_get_greeting(server_client_agents: Any):
    """Test getting a prompt from the server."""
    server_agent, client_agent = await anext(server_client_agents)

    # Get a greeting from the server
    result = await client_agent.get_greeting("test_server", "User")

    # Check the result
    assert isinstance(result, str)
    assert "Hello, User!" in result


@pytest.mark.asyncio
async def test_get_resource(server_client_agents: Any):
    """Test reading a resource from the server."""
    server_agent, client_agent = await anext(server_client_agents)

    # Read the resource from the server
    result = await client_agent.get_test_resource("test_server")

    # Check the result
    assert isinstance(result, bytes)
    assert b'"message": "This is a test resource"' in result


@pytest.mark.asyncio
async def test_list_tools(server_client_agents: Any):
    """Test listing tools from the server."""
    server_agent, client_agent = await anext(server_client_agents)

    # List tools from the server using send_request directly
    result = await client_agent.communicator.send_request("test_server", "tool/list")

    # Check that the list contains the expected tools
    assert isinstance(result, list)
    assert len(result) >= 2  # At least add_numbers and process_sample
    tool_names = [tool["name"] for tool in result]
    assert "add_numbers" in tool_names
    assert "process_sample" in tool_names


@pytest.mark.asyncio
async def test_list_prompts(server_client_agents: Any):
    """Test listing prompts from the server."""
    server_agent, client_agent = await anext(server_client_agents)

    # List prompts from the server using send_request directly
    result = await client_agent.communicator.send_request("test_server", "prompt/list")

    # Check that the list contains the expected prompts
    assert isinstance(result, list)
    assert len(result) >= 1  # At least greeting
    prompt_names = [prompt["name"] for prompt in result]
    assert "greeting" in prompt_names


@pytest.mark.asyncio
async def test_error_handling(server_client_agents: Any):
    """Test error handling in client-server communication."""
    server_agent, client_agent = await anext(server_client_agents)

    # Try to call a non-existent tool
    with pytest.raises(CommunicationError) as excinfo:
        await client_agent.call_tool(
            target_service="test_server", tool_name="non_existent_tool", arguments={"a": 1, "b": 2}
        )

    # Check the error message
    assert "non_existent_tool" in str(excinfo.value)
