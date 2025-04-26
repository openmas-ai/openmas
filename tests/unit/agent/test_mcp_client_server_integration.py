"""Integration tests for MCP client-server interaction."""

import asyncio
from typing import Dict, Tuple

import pytest
from pydantic import BaseModel

from openmas.agent import McpClientAgent, McpServerAgent
from openmas.agent.config import AgentConfig
from openmas.agent.mcp import mcp_prompt, mcp_resource, mcp_tool
from openmas.communication.exception import CommunicationError
from openmas.communication.mcp import McpSseCommunicator

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
    """Create and setup a server and client agent pair.

    Returns:
        Tuple of (server_agent, client_agent)
    """
    global ports_used
    # Set up a unique port for this test
    if "mcp_client_server_tests" not in ports_used:
        ports_used["mcp_client_server_tests"] = 0
    port = 9000 + ports_used["mcp_client_server_tests"]
    ports_used["mcp_client_server_tests"] += 1

    # Create server agent
    server_config = AgentConfig(name="test_server")
    server_agent = TestServerAgent(config=server_config, server_type="sse", host="localhost", port=port)

    # Create client agent
    client_config = AgentConfig(name="test_client")
    client_agent = TestClientAgent(config=client_config)

    # Set up client communicator
    client_communicator = McpSseCommunicator(
        agent_name="test_client", service_urls={"test_server": f"http://localhost:{port}/mcp"}
    )
    client_agent.set_communicator(client_communicator)

    # Start the server
    await server_agent.setup()
    await server_agent.start_server()

    # Give server time to start
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            ready = await server_agent.wait_until_ready(timeout=1.0)
            if ready:
                break
            await asyncio.sleep(0.5)
        except Exception:
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(0.5)

    # Set up client
    await client_agent.setup()

    try:
        # Return the agents for the test
        yield server_agent, client_agent
    finally:
        # Clean up
        await client_agent.shutdown()
        await server_agent.shutdown()


# Add proper typing for pytest.ports_used
if not hasattr(pytest, "ports_used"):
    setattr(pytest, "ports_used", {})
# Ensure it's properly typed for mypy
ports_used: Dict[str, int] = pytest.ports_used  # type: ignore


@pytest.mark.asyncio
async def test_call_add_numbers(server_client_agents: Tuple[TestServerAgent, TestClientAgent]):
    """Test calling the add_numbers tool."""
    async for server_agent, client_agent in [server_client_agents]:
        # Call the add_numbers tool
        result = await client_agent.call_add_numbers("test_server", 5, 7)

        # Check the result
        assert isinstance(result, dict)
        assert "result" in result
        assert result["result"] == 12


@pytest.mark.asyncio
async def test_call_process_sample(server_client_agents: Tuple[TestServerAgent, TestClientAgent]):
    """Test calling the process_sample tool with Pydantic models."""
    async for server_agent, client_agent in [server_client_agents]:
        # Call the process_sample tool
        result = await client_agent.call_process_sample("test_server", "test", 42)

        # Check the result
        assert isinstance(result, dict)
        assert "result" in result
        assert "status" in result
        assert result["status"] == 200
        assert "Processed test with value 42" in result["result"]


@pytest.mark.asyncio
async def test_get_greeting(server_client_agents: Tuple[TestServerAgent, TestClientAgent]):
    """Test getting a prompt from the server."""
    async for server_agent, client_agent in [server_client_agents]:
        # Get the greeting prompt
        result = await client_agent.get_greeting("test_server", "Bob")

        # Check the result
        assert isinstance(result, str)
        assert "Hello, Bob!" in result


@pytest.mark.asyncio
async def test_get_resource(server_client_agents: Tuple[TestServerAgent, TestClientAgent]):
    """Test reading a resource from the server."""
    async for server_agent, client_agent in [server_client_agents]:
        # Get the test resource
        result = await client_agent.get_test_resource("test_server")

        # Check the result
        assert isinstance(result, bytes)
        assert b"This is a test resource" in result


@pytest.mark.asyncio
async def test_list_tools(server_client_agents: Tuple[TestServerAgent, TestClientAgent]):
    """Test listing tools from the server."""
    async for server_agent, client_agent in [server_client_agents]:
        # List the tools
        tools = await client_agent.list_tools("test_server")

        # Check the result
        assert isinstance(tools, list)
        assert len(tools) >= 2  # Should have at least add_numbers and process_sample

        # Find our tools in the list
        add_numbers_tool = next((t for t in tools if t["name"] == "add_numbers"), None)
        process_sample_tool = next((t for t in tools if t["name"] == "process_sample"), None)

        # Verify tools were found
        assert add_numbers_tool is not None
        assert process_sample_tool is not None
        assert "Add two numbers together" in add_numbers_tool["description"]


@pytest.mark.asyncio
async def test_list_prompts(server_client_agents: Tuple[TestServerAgent, TestClientAgent]):
    """Test listing prompts from the server."""
    async for server_agent, client_agent in [server_client_agents]:
        # List the prompts
        prompts = await client_agent.list_prompts("test_server")

        # Check the result
        assert isinstance(prompts, list)
        assert len(prompts) >= 1  # Should have at least greeting

        # Find our prompt in the list
        greeting_prompt = next((p for p in prompts if p["name"] == "greeting"), None)

        # Verify prompt was found
        assert greeting_prompt is not None
        assert "Generate a greeting" in greeting_prompt["description"]


@pytest.mark.asyncio
async def test_error_handling(server_client_agents: Tuple[TestServerAgent, TestClientAgent]):
    """Test error handling in client-server communication."""
    async for server_agent, client_agent in [server_client_agents]:
        # Attempt to call a non-existent tool
        with pytest.raises(CommunicationError):
            await client_agent.call_tool(target_service="test_server", tool_name="non_existent_tool", arguments={})

        # Attempt to connect to non-existent server
        non_existent_communicator = McpSseCommunicator(
            agent_name="test_client",
            service_urls={"non_existent": "http://localhost:60000/mcp"},  # Using a port that's likely not in use
        )

        client_agent.set_communicator(non_existent_communicator)

        with pytest.raises(CommunicationError):
            await client_agent.call_tool(target_service="non_existent", tool_name="add_numbers", arguments={"a": 1, "b": 2})
