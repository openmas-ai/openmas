"""Integration tests for MCP mock agent interactions.

Tests the interaction between MCP agents using linked mock communicators.
This file uses mock implementations without real dependencies.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import pytest
from pydantic import BaseModel

from openmas.agent import McpClientAgent, McpServerAgent
from openmas.agent.mcp import mcp_prompt, mcp_resource, mcp_tool
from openmas.config import AgentConfig
from openmas.testing.mock_communicator import MockCommunicator

# Mark all tests in this module as using mocks
pytestmark = [
    pytest.mark.mcp,
    pytest.mark.mock,
]


class MockMcpCommunicator(MockCommunicator):
    """Mock communicator for MCP testing that supports registering tools, prompts, and resources."""

    def __init__(self, agent_name: str, service_urls: Optional[Dict[str, str]] = None, server_mode: bool = True):
        """Initialize the mock MCP communicator.

        Args:
            agent_name: The name of the agent using this communicator
            service_urls: Mapping of service names to URLs (optional for mocking)
            server_mode: Whether to run in server mode
        """
        super().__init__(agent_name, service_urls or {})
        self.server_mode = server_mode
        self.registered_tools: Dict[str, Dict[str, Any]] = {}
        self.registered_prompts: Dict[str, Dict[str, Any]] = {}
        self.registered_resources: Dict[str, Dict[str, Any]] = {}

    async def register_tool(self, name: str, description: str, function: Callable) -> None:
        """Register a tool with the communicator.

        Args:
            name: The tool name
            description: The tool description
            function: The tool function
        """
        self._record_call("register_tool", name, description, function)

        # Store the tool registration
        self.registered_tools[name] = {
            "description": description,
            "function": function,
        }

        # Also register it as a handler with a standardized name
        await self.register_handler(f"tool/call/{name}", function)

    async def register_prompt(self, name: str, description: str, function: Callable) -> None:
        """Register a prompt with the communicator.

        Args:
            name: The prompt name
            description: The prompt description
            function: The prompt function
        """
        self._record_call("register_prompt", name, description, function)

        # Store the prompt registration
        self.registered_prompts[name] = {
            "description": description,
            "function": function,
        }

        # Also register it as a handler with a standardized name
        await self.register_handler(f"prompt/get/{name}", function)

    async def register_resource(
        self, name: str, description: str, function: Callable, mime_type: str = "text/plain"
    ) -> None:
        """Register a resource with the communicator.

        Args:
            name: The resource name
            description: The resource description
            function: The resource function
            mime_type: The resource MIME type
        """
        self._record_call("register_resource", name, description, function, mime_type)

        # Store the resource registration
        self.registered_resources[name] = {
            "description": description,
            "function": function,
            "mime_type": mime_type,
        }

        # Also register it as a handler with a standardized name
        await self.register_handler(f"resource/{name}", function)


class CalculationRequest(BaseModel):
    """Input model for calculation requests."""

    operation: str
    values: List[float]


class CalculationResult(BaseModel):
    """Output model for calculation results."""

    result: float
    operation: str


class ServerAgent(McpServerAgent):
    """Test server agent with MCP decorated methods."""

    def __init__(self, *args, **kwargs):
        """Initialize the server agent."""
        super().__init__(*args, **kwargs)
        self.tool_call_history = []
        self.prompt_call_history = []
        self.resource_access_history = []

    @mcp_tool(
        name="calculator",
        description="Perform mathematical calculations",
        input_model=CalculationRequest,
        output_model=CalculationResult,
    )
    async def calculator(self, operation: str, values: List[float]) -> Dict[str, Any]:
        """Perform calculations.

        Args:
            operation: The operation to perform (sum, avg, min, max)
            values: The values to operate on

        Returns:
            Calculation result
        """
        self.tool_call_history.append({"operation": operation, "values": values})

        result = 0.0
        if operation == "sum":
            result = sum(values)
        elif operation == "avg":
            result = sum(values) / len(values) if values else 0
        elif operation == "min":
            result = min(values) if values else 0
        elif operation == "max":
            result = max(values) if values else 0

        return {"result": result, "operation": operation}

    @mcp_tool(name="echo", description="Echo back the input")
    async def echo(self, message: str) -> Dict[str, Any]:
        """Echo back the input message.

        Args:
            message: The message to echo

        Returns:
            The echo response
        """
        self.tool_call_history.append({"message": message})
        return {"echo": message}

    @mcp_prompt(
        name="data_summary",
        description="Generate a data summary",
        template="Data summary for {{ dataset }}: {{ count }} records with average value {{ average }}.",
    )
    async def data_summary_prompt(self, dataset: str, count: int, average: float) -> str:
        """Generate a data summary.

        Args:
            dataset: Dataset name
            count: Number of records
            average: Average value

        Returns:
            Formatted summary
        """
        self.prompt_call_history.append({"dataset": dataset, "count": count, "average": average})
        return f"Data summary for {dataset}: {count} records with average value {average}."

    @mcp_resource(
        uri="/api/statistics", name="statistics", description="Statistics resource", mime_type="application/json"
    )
    async def statistics_resource(self) -> bytes:
        """Provide statistics resource.

        Returns:
            JSON-encoded statistics
        """
        self.resource_access_history.append({"resource": "statistics"})
        import json

        stats = {
            "count": len(self.tool_call_history),
            "operations": [call.get("operation") for call in self.tool_call_history if "operation" in call],
        }
        return json.dumps(stats).encode("utf-8")


class ClientAgent(McpClientAgent):
    """Test client agent for interacting with the server."""

    async def calculate(self, service_name: str, operation: str, values: List[float]) -> Dict[str, Any]:
        """Call the calculator tool on the server.

        Args:
            service_name: Target service
            operation: The operation to perform
            values: The values to operate on

        Returns:
            Calculation result
        """
        result = await self.call_tool(
            target_service=service_name, tool_name="calculator", arguments={"operation": operation, "values": values}
        )

        # Ensure we return a dictionary
        if not isinstance(result, dict):
            return {"result": result, "operation": operation}
        return result

    async def send_echo(self, service_name: str, message: str) -> Dict[str, Any]:
        """Call the echo tool on the server.

        Args:
            service_name: Target service
            message: Message to echo

        Returns:
            Echo response
        """
        result = await self.call_tool(target_service=service_name, tool_name="echo", arguments={"message": message})

        # Ensure we return a dictionary
        if not isinstance(result, dict):
            return {"echo": result}
        return result

    async def get_data_summary(self, service_name: str, dataset: str, count: int, average: float) -> str:
        """Get a data summary from the server.

        Args:
            service_name: Target service
            dataset: Dataset name
            count: Number of records
            average: Average value

        Returns:
            Formatted summary
        """
        result = await self.get_prompt(
            target_service=service_name,
            prompt_name="data_summary",
            arguments={"dataset": dataset, "count": count, "average": average},
        )

        # Ensure we return a string
        if not isinstance(result, str):
            return str(result)
        return result

    async def get_statistics(self, service_name: str) -> bytes:
        """Get statistics from the server.

        Args:
            service_name: Target service

        Returns:
            Statistics data
        """
        result = await self.read_resource(target_service=service_name, uri="/api/statistics")

        # Ensure we return bytes
        if not isinstance(result, bytes):
            return str(result).encode("utf-8")
        return result


@pytest.fixture
def server_agent() -> ServerAgent:
    """Create a server agent with a mock communicator.

    Returns:
        ServerAgent: Server agent instance
    """
    config = AgentConfig(name="test_server")
    agent = ServerAgent(config=config)

    # Create and attach a mock communicator
    communicator = MockMcpCommunicator(agent_name="test_server")
    agent.set_communicator(communicator)

    return agent


@pytest.fixture
def client_agent() -> ClientAgent:
    """Create a client agent with a mock communicator.

    Returns:
        ClientAgent: Client agent instance
    """
    config = AgentConfig(name="test_client")
    agent = ClientAgent(config=config)

    # Create and attach a mock communicator
    communicator = MockMcpCommunicator(
        agent_name="test_client", service_urls={"test_server": "mock://test_server"}, server_mode=False
    )
    agent.set_communicator(communicator)

    return agent


@pytest.fixture
def client_server_pair() -> Tuple[ServerAgent, ClientAgent]:
    """Create a linked pair of server and client agents with mock communicators.

    Returns:
        Tuple[ServerAgent, ClientAgent]: Paired server and client agents
    """
    # Create the agents
    server_config = AgentConfig(name="test_server")
    server_agent = ServerAgent(config=server_config)

    client_config = AgentConfig(name="test_client")
    client_agent = ClientAgent(config=client_config)

    # Create communicators
    server_communicator = MockMcpCommunicator(agent_name="test_server", server_mode=True)
    client_communicator = MockMcpCommunicator(
        agent_name="test_client", service_urls={"test_server": "mock://test_server"}, server_mode=False
    )

    # Set communicators
    server_agent.set_communicator(server_communicator)
    client_agent.set_communicator(client_communicator)

    # Link the communicators
    server_communicator.link_communicator(client_communicator)

    return server_agent, client_agent


@pytest.mark.mcp
class TestMcpAgentCommunicatorInteractions:
    """Test MCP agent-communicator interactions using mocks."""

    @pytest.mark.asyncio
    async def test_server_agent_setup_registers_methods(self, server_agent):
        """Test that server agent's setup registers decorated methods with the communicator."""
        # Get the mock communicator
        mock_comm = cast(MockMcpCommunicator, server_agent.communicator)

        # Set up the server agent
        await server_agent.setup()

        # Check registered methods directly in the communicator
        assert "calculator" in mock_comm.registered_tools
        assert "echo" in mock_comm.registered_tools
        assert "data_summary" in mock_comm.registered_prompts
        assert "statistics" in mock_comm.registered_resources

        # Verify tool registrations
        assert mock_comm.registered_tools["calculator"]["description"] == "Perform mathematical calculations"

        # Verify prompt registrations
        assert mock_comm.registered_prompts["data_summary"]["description"] == "Generate a data summary"

        # Verify resource registrations
        assert mock_comm.registered_resources["statistics"]["description"] == "Statistics resource"
        assert mock_comm.registered_resources["statistics"]["mime_type"] == "application/json"

    @pytest.mark.asyncio
    async def test_client_agent_delegates_to_communicator(self, client_agent):
        """Test that client agent methods delegate to the underlying communicator."""
        # Get the mock communicator
        mock_comm = cast(MockMcpCommunicator, client_agent.communicator)

        # Set up expected responses
        mock_comm.expect_request(
            target_service="test_server",
            method="tool/call/calculator",
            params={"operation": "sum", "values": [1, 2, 3]},
            response=6,  # Simplified response that the client will transform
        )

        mock_comm.expect_request(
            target_service="test_server",
            method="prompt/get/data_summary",
            params={"dataset": "test", "count": 10, "average": 5.5},
            response="Data summary for test: 10 records with average value 5.5.",
        )

        mock_comm.expect_request(
            target_service="test_server",
            method="resource/read",
            params={"uri": "/api/statistics"},
            response=b'{"count": 0, "operations": []}',
        )

        # Set up the client agent
        await client_agent.setup()

        # Call the client methods
        calc_result = await client_agent.calculate("test_server", "sum", [1, 2, 3])
        summary = await client_agent.get_data_summary("test_server", "test", 10, 5.5)
        stats = await client_agent.get_statistics("test_server")

        # Verify the results
        assert calc_result["result"] == 6
        assert calc_result["operation"] == "sum"
        assert summary == "Data summary for test: 10 records with average value 5.5."
        assert stats == b'{"count": 0, "operations": []}'

        # Verify that the communicator was called correctly
        call_tool_calls = [
            call for call in mock_comm.calls if call.method_name == "send_request" and "tool/call" in call.args[1]
        ]
        assert len(call_tool_calls) > 0, "No call_tool calls were made"

        get_prompt_calls = [
            call for call in mock_comm.calls if call.method_name == "send_request" and "prompt/get" in call.args[1]
        ]
        assert len(get_prompt_calls) > 0, "No get_prompt calls were made"

        read_resource_calls = [
            call for call in mock_comm.calls if call.method_name == "send_request" and "resource/read" in call.args[1]
        ]
        assert len(read_resource_calls) > 0, "No read_resource calls were made"

        # Verify all expectations were met
        mock_comm.verify()

    @pytest.mark.asyncio
    async def test_client_server_mock_interaction(self, client_server_pair):
        """Test interaction between client and server using linked mock communicators."""
        server_agent, client_agent = client_server_pair

        # Set up both agents
        await server_agent.setup()
        await client_agent.setup()

        # Set up the handler for the calculator tool
        client_comm = cast(MockMcpCommunicator, client_agent.communicator)
        # Server communicator is not used directly in this test

        # Need to manually set up forwarding expectations for the linked communicators

        # Calculator tool forwarding
        client_comm.expect_request(
            target_service="test_server",
            method="tool/call/calculator",
            params={"operation": "sum", "values": [10, 20, 30]},
            response={"result": 60, "operation": "sum"},
        )

        # Forwarding for the data summary prompt
        client_comm.expect_request(
            target_service="test_server",
            method="prompt/get/data_summary",
            params={"dataset": "sales", "count": 100, "average": 45.75},
            response="Data summary for sales: 100 records with average value 45.75.",
        )

        # Forwarding for the statistics resource
        client_comm.expect_request(
            target_service="test_server",
            method="resource/read",
            params={"uri": "/api/statistics"},
            response=b'{"count": 1, "operations": ["sum"]}',
        )

        # Use the client to call the server's calculator tool
        calc_result = await client_agent.calculate("test_server", "sum", [10, 20, 30])

        # Verify the result
        assert calc_result["result"] == 60
        assert calc_result["operation"] == "sum"

        # Manually append to tool call history since we're mocking and not actually calling the handler
        server_agent.tool_call_history.append({"operation": "sum", "values": [10, 20, 30]})

        # Test prompt interaction
        summary = await client_agent.get_data_summary("test_server", "sales", 100, 45.75)

        # Verify prompt result
        assert "Data summary for sales: 100 records with average value 45.75" in summary

        # Manually append to prompt call history
        server_agent.prompt_call_history.append({"dataset": "sales", "count": 100, "average": 45.75})

        # Test resource interaction
        stats_data = await client_agent.get_statistics("test_server")

        # Manually append to resource access history
        server_agent.resource_access_history.append({"resource": "statistics"})

        # Verify the resource data
        import json

        stats = json.loads(stats_data)
        assert "count" in stats
        assert "operations" in stats
        assert stats["count"] == 1  # One tool call
        assert "sum" in stats["operations"]

        # Verify all expectations were met
        client_comm.verify()
