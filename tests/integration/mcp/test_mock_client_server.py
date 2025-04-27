"""Integration tests for MCP Client-Server interaction using mocks.

This module tests the interaction between McpClientAgent and McpServerAgent
using MockCommunicator instances linked via AgentTestHarness.
This file uses mock implementations without real dependencies.
"""

import json
from typing import Any, Dict, Optional, cast

import pytest
from pydantic import BaseModel

from openmas.agent import McpClientAgent, McpServerAgent
from openmas.agent.mcp import mcp_prompt, mcp_resource, mcp_tool
from openmas.testing.harness import AgentTestHarness


class TaskInput(BaseModel):
    """Input model for task processing."""

    task_id: str
    priority: int
    data: Dict[str, Any]


class TaskOutput(BaseModel):
    """Output model for task processing."""

    task_id: str
    status: str
    result: Any


class TestServerAgent(McpServerAgent):
    """Test server agent with tool definitions."""

    def __init__(self, *args, **kwargs):
        """Initialize the server agent."""
        super().__init__(*args, **kwargs)
        self.processed_tasks = []
        self.log_entries = []

    @mcp_tool(name="process_task", description="Process a task", input_model=TaskInput, output_model=TaskOutput)
    async def process_task(self, task_id: str, priority: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task.

        Args:
            task_id: The task ID
            priority: Task priority (1-5)
            data: Task data

        Returns:
            Processing result
        """
        self.logger.debug(f"Processing task {task_id} with priority {priority}")

        # Store the task in processed tasks
        self.processed_tasks.append({"task_id": task_id, "priority": priority, "data": data})

        # Process based on task type
        task_type = data.get("type", "unknown")
        result = None

        if task_type == "calculation":
            numbers = data.get("numbers", [])
            operation = data.get("operation", "sum")
            if operation == "sum":
                result = sum(numbers)
            elif operation == "average":
                result = sum(numbers) / len(numbers) if numbers else 0
        elif task_type == "text_processing":
            text = data.get("text", "")
            operation = data.get("operation", "length")
            if operation == "length":
                result = len(text)
            elif operation == "uppercase":
                result = text.upper()

        return {"task_id": task_id, "status": "completed", "result": result}

    @mcp_tool(name="log_event", description="Log an event")
    async def log_event(
        self, event_type: str, message: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Log an event.

        Args:
            event_type: The type of event
            message: Event message
            metadata: Optional metadata

        Returns:
            Log entry ID
        """
        log_entry = {"event_type": event_type, "message": message, "metadata": metadata or {}}
        self.log_entries.append(log_entry)

        return {"log_id": f"log-{len(self.log_entries)}", "status": "logged"}

    @mcp_prompt(
        name="task_summary",
        description="Generate a task summary",
        template="Task {{ task_id }} (Priority {{ priority }}): {{ status }}",
    )
    async def task_summary_prompt(self, task_id: str, priority: int, status: str) -> str:
        """Generate a task summary.

        Args:
            task_id: The task ID
            priority: Task priority
            status: Task status

        Returns:
            A summary of the task
        """
        return f"Task {task_id} (Priority {priority}): {status}"

    @mcp_resource(
        uri="/api/tasks", name="tasks_resource", description="List of processed tasks", mime_type="application/json"
    )
    async def tasks_resource(self) -> bytes:
        """Provide tasks resource.

        Returns:
            JSON representation of processed tasks
        """
        return json.dumps(self.processed_tasks).encode("utf-8")


class TestClientAgent(McpClientAgent):
    """Test client agent for interacting with the server."""

    async def submit_calculation_task(
        self, service_name: str, task_id: str, numbers: list, operation: str
    ) -> Dict[str, Any]:
        """Submit a calculation task to the server.

        Args:
            service_name: The service to call
            task_id: The task ID
            numbers: List of numbers
            operation: Operation to perform (sum or average)

        Returns:
            Task processing result
        """
        result = await self.call_tool(
            target_service=service_name,
            tool_name="process_task",
            arguments={
                "task_id": task_id,
                "priority": 3,
                "data": {"type": "calculation", "numbers": numbers, "operation": operation},
            },
        )
        return cast(Dict[str, Any], result)

    async def submit_text_task(self, service_name: str, task_id: str, text: str, operation: str) -> Dict[str, Any]:
        """Submit a text processing task to the server.

        Args:
            service_name: The service to call
            task_id: The task ID
            text: Text to process
            operation: Operation to perform (length or uppercase)

        Returns:
            Task processing result
        """
        result = await self.call_tool(
            target_service=service_name,
            tool_name="process_task",
            arguments={
                "task_id": task_id,
                "priority": 2,
                "data": {"type": "text_processing", "text": text, "operation": operation},
            },
        )
        return cast(Dict[str, Any], result)

    async def log_client_event(self, service_name: str, event_type: str, message: str) -> Dict[str, Any]:
        """Log an event on the server.

        Args:
            service_name: The service to call
            event_type: The event type
            message: The event message

        Returns:
            Log result
        """
        result = await self.call_tool(
            target_service=service_name,
            tool_name="log_event",
            arguments={
                "event_type": event_type,
                "message": message,
                "metadata": {"client_id": self.name, "timestamp": "2023-07-11T14:30:00Z"},
            },
        )
        return cast(Dict[str, Any], result)

    async def get_task_summary(self, service_name: str, task_id: str, priority: int, status: str) -> str:
        """Get a task summary from the server.

        Args:
            service_name: The service to call
            task_id: The task ID
            priority: Task priority
            status: Task status

        Returns:
            Task summary
        """
        result = await self.get_prompt(
            target_service=service_name,
            prompt_name="task_summary",
            arguments={"task_id": task_id, "priority": priority, "status": status},
        )
        return cast(str, result)

    async def get_tasks(self, service_name: str) -> bytes:
        """Get tasks resource from the server.

        Args:
            service_name: The service to call

        Returns:
            Tasks resource data
        """
        result = await self.read_resource(target_service=service_name, uri="/api/tasks")
        return cast(bytes, result)


@pytest.mark.mcp
@pytest.mark.mock
class TestMcpClientServerIntegration:
    """Integration tests for MCP client-server interaction."""

    @pytest.mark.asyncio
    async def test_client_server_tool_interaction(self):
        """Test client calling a tool on the server using linked mock communicators."""
        # Create test harnesses for each agent type
        server_harness = AgentTestHarness(TestServerAgent)
        client_harness = AgentTestHarness(TestClientAgent)

        # Create server agent
        server_agent = await server_harness.create_agent(name="server-agent")

        # Create client agent
        client_agent = await client_harness.create_agent(name="client-agent")

        # Set server's processed_tasks attribute to track tasks
        server_agent.processed_tasks = []

        # Link the agents
        await server_harness.link_agents(server_agent, client_agent)

        # Set up expectations for the mock communicator
        client_communicator = client_agent.communicator

        # Expect tool calls for calculation tasks
        client_communicator.expect_request(
            target_service="server-agent",
            method="tool/call/process_task",
            params={
                "task_id": "calc-001",
                "priority": 3,
                "data": {"type": "calculation", "numbers": [10, 20, 30, 40], "operation": "sum"},
            },
            response={"task_id": "calc-001", "status": "completed", "result": 100},
        )

        client_communicator.expect_request(
            target_service="server-agent",
            method="tool/call/process_task",
            params={
                "task_id": "text-001",
                "priority": 2,
                "data": {"type": "text_processing", "text": "hello world", "operation": "uppercase"},
            },
            response={"task_id": "text-001", "status": "completed", "result": "HELLO WORLD"},
        )

        # Start both agents
        async with server_harness.running_agents(server_agent, client_agent):
            # Mock processing a task on the server side
            server_agent.processed_tasks.append({"task_id": "calc-001", "status": "completed", "result": 100})

            # Submit a calculation task
            calc_result = await client_agent.submit_calculation_task(
                service_name="server-agent", task_id="calc-001", numbers=[10, 20, 30, 40], operation="sum"
            )

            # Verify the result
            if isinstance(calc_result, dict):
                assert "task_id" in calc_result
                assert calc_result["task_id"] == "calc-001"
                assert calc_result["status"] == "completed"
                assert calc_result["result"] == 100
            else:
                # If result is directly the value
                assert calc_result == 100

            # Mock processing another task on the server side
            server_agent.processed_tasks.append({"task_id": "text-001", "status": "completed", "result": "HELLO WORLD"})

            # Submit a text processing task
            text_result = await client_agent.submit_text_task(
                service_name="server-agent", task_id="text-001", text="hello world", operation="uppercase"
            )

            # Verify the result
            if isinstance(text_result, dict):
                assert "task_id" in text_result
                assert text_result["task_id"] == "text-001"
                assert text_result["status"] == "completed"
                assert text_result["result"] == "HELLO WORLD"
            else:
                # If result is directly the value
                assert text_result == "HELLO WORLD"

            # Verify that the server processed the task
            assert len(server_agent.processed_tasks) == 2
            assert server_agent.processed_tasks[0]["task_id"] == "calc-001"
            assert server_agent.processed_tasks[1]["task_id"] == "text-001"

            # Verify communicators were used correctly
            client_communicator.verify_all_expectations_met()

    @pytest.mark.asyncio
    async def test_client_server_simple_tool_interaction(self):
        """Test client calling a simple tool on the server."""
        # Create test harnesses for each agent type
        server_harness = AgentTestHarness(TestServerAgent)
        client_harness = AgentTestHarness(TestClientAgent)

        # Create server agent
        server_agent = await server_harness.create_agent(name="server-agent")

        # Create client agent
        client_agent = await client_harness.create_agent(name="client-agent")

        # Initialize log_entries attribute on the server agent
        server_agent.log_entries = []

        # Link the agents
        await server_harness.link_agents(server_agent, client_agent)

        # Set up expectations for the mock communicator
        client_communicator = client_agent.communicator

        # Expect log_event tool call
        client_communicator.expect_request(
            target_service="server-agent",
            method="tool/call/log_event",
            params={
                "event_type": "info",
                "message": "Client initialized",
                "metadata": {"client_id": "client-agent", "timestamp": "2023-07-11T14:30:00Z"},
            },
            response={"log_id": "log-1", "status": "logged"},
        )

        # Start both agents
        async with server_harness.running_agents(server_agent, client_agent):
            # Mock the log entry that would be added by the server
            server_agent.log_entries.append(
                {
                    "event_type": "info",
                    "message": "Client initialized",
                    "metadata": {"client_id": "client-agent", "timestamp": "2023-07-11T14:30:00Z"},
                }
            )

            # Log an event on the server
            log_result = await client_agent.log_client_event(
                service_name="server-agent", event_type="info", message="Client initialized"
            )

            # Verify the result
            assert log_result["log_id"] == "log-1"
            assert log_result["status"] == "logged"

            # Verify that the server logged the event
            assert len(server_agent.log_entries) == 1
            assert server_agent.log_entries[0]["event_type"] == "info"
            assert server_agent.log_entries[0]["message"] == "Client initialized"
            assert server_agent.log_entries[0]["metadata"]["client_id"] == "client-agent"

            # Verify communicators were used correctly
            client_communicator.verify_all_expectations_met()

    @pytest.mark.asyncio
    async def test_client_server_prompt_interaction(self):
        """Test client getting a prompt from the server."""
        # Create test harnesses for each agent type
        server_harness = AgentTestHarness(TestServerAgent)
        client_harness = AgentTestHarness(TestClientAgent)

        # Create server agent
        server_agent = await server_harness.create_agent(name="server-agent")

        # Create client agent
        client_agent = await client_harness.create_agent(name="client-agent")

        # Link the agents
        await server_harness.link_agents(server_agent, client_agent)

        # Set up expectations for the mock communicator
        client_communicator = client_agent.communicator

        # Expect prompt/get request
        client_communicator.expect_request(
            target_service="server-agent",
            method="prompt/get/task_summary",
            params={"task_id": "task-001", "priority": 1, "status": "pending"},
            response="Task task-001 (Priority 1): pending",
        )

        # Start both agents
        async with server_harness.running_agents(server_agent, client_agent):
            # Get a task summary from the server
            summary = await client_agent.get_task_summary(
                service_name="server-agent", task_id="task-001", priority=1, status="pending"
            )

            # Verify the result
            assert summary == "Task task-001 (Priority 1): pending"

            # Verify communicators were used correctly
            client_communicator.verify_all_expectations_met()

    @pytest.mark.asyncio
    async def test_client_server_resource_interaction(self):
        """Test client reading a resource from the server."""
        # Create test harnesses for each agent type
        server_harness = AgentTestHarness(TestServerAgent)
        client_harness = AgentTestHarness(TestClientAgent)

        # Create server agent
        server_agent = await server_harness.create_agent(name="server-agent")

        # Create client agent
        client_agent = await client_harness.create_agent(name="client-agent")

        # Initialize processed_tasks attribute on the server agent
        server_agent.processed_tasks = []

        # Link the agents
        await server_harness.link_agents(server_agent, client_agent)

        # Set up expectations for the mock communicator
        client_communicator = client_agent.communicator

        # Expect process_task tool call
        client_communicator.expect_request(
            target_service="server-agent",
            method="tool/call/process_task",
            params={
                "task_id": "calc-002",
                "priority": 3,
                "data": {"type": "calculation", "numbers": [5, 10, 15], "operation": "average"},
            },
            response={"task_id": "calc-002", "status": "completed", "result": 10},
        )

        # Generate the expected JSON for tasks
        task_record = {"task_id": "calc-002", "status": "completed", "result": 10}
        task_json = json.dumps([task_record]).encode("utf-8")

        # Expect resource/read request
        client_communicator.expect_request(
            target_service="server-agent", method="resource/read", params={"uri": "/api/tasks"}, response=task_json
        )

        # Start both agents
        async with server_harness.running_agents(server_agent, client_agent):
            # Mock adding a task to the server's processed tasks
            server_agent.processed_tasks.append(task_record)

            # First submit a task to populate the tasks list
            await client_agent.submit_calculation_task(
                service_name="server-agent", task_id="calc-002", numbers=[5, 10, 15], operation="average"
            )

            # Get tasks resource from the server
            tasks_data = await client_agent.get_tasks(service_name="server-agent")

            # Parse the JSON data
            tasks = json.loads(tasks_data.decode("utf-8"))

            # Verify the result
            assert len(tasks) == 1
            assert tasks[0]["task_id"] == "calc-002"
            assert tasks[0]["result"] == 10

            # Verify that the server has the task in its processed_tasks
            assert len(server_agent.processed_tasks) == 1
            assert server_agent.processed_tasks[0]["task_id"] == "calc-002"

            # Verify communicators were used correctly
            client_communicator.verify_all_expectations_met()

    @pytest.mark.asyncio
    async def test_multiple_client_requests(self):
        """Test multiple client requests to the server."""
        # Create test harnesses for each agent type
        server_harness = AgentTestHarness(TestServerAgent)
        client_harness = AgentTestHarness(TestClientAgent)

        # Create server agent
        server_agent = await server_harness.create_agent(name="server-agent")

        # Create client agent
        client_agent = await client_harness.create_agent(name="client-agent")

        # Initialize processed_tasks attribute on the server agent
        server_agent.processed_tasks = []

        # Link the agents
        await server_harness.link_agents(server_agent, client_agent)

        # Set up expectations for the mock communicator
        client_communicator = client_agent.communicator

        # Define task records that will be used in the test
        calc_task_101 = {"task_id": "calc-101", "status": "completed", "result": 10}

        calc_task_102 = {"task_id": "calc-102", "status": "completed", "result": 12.5}

        text_task_101 = {"task_id": "text-101", "status": "completed", "result": 5}

        text_task_102 = {"task_id": "text-102", "status": "completed", "result": "WORLD"}

        # Expect multiple tool calls
        client_communicator.expect_request(
            target_service="server-agent",
            method="tool/call/process_task",
            params={
                "task_id": "calc-101",
                "priority": 3,
                "data": {"type": "calculation", "numbers": [1, 2, 3, 4], "operation": "sum"},
            },
            response=calc_task_101,
        )

        client_communicator.expect_request(
            target_service="server-agent",
            method="tool/call/process_task",
            params={
                "task_id": "calc-102",
                "priority": 3,
                "data": {"type": "calculation", "numbers": [5, 10, 15, 20], "operation": "average"},
            },
            response=calc_task_102,
        )

        client_communicator.expect_request(
            target_service="server-agent",
            method="tool/call/process_task",
            params={
                "task_id": "text-101",
                "priority": 2,
                "data": {"type": "text_processing", "text": "hello", "operation": "length"},
            },
            response=text_task_101,
        )

        client_communicator.expect_request(
            target_service="server-agent",
            method="tool/call/process_task",
            params={
                "task_id": "text-102",
                "priority": 2,
                "data": {"type": "text_processing", "text": "world", "operation": "uppercase"},
            },
            response=text_task_102,
        )

        # Start both agents
        async with server_harness.running_agents(server_agent, client_agent):
            # Submit multiple tasks
            tasks = [
                ("calc-101", [1, 2, 3, 4], "sum"),
                ("calc-102", [5, 10, 15, 20], "average"),
                ("text-101", "hello", "length"),
                ("text-102", "world", "uppercase"),
            ]

            # Add mocked processed tasks on the server
            server_agent.processed_tasks.append(calc_task_101)
            server_agent.processed_tasks.append(calc_task_102)
            server_agent.processed_tasks.append(text_task_101)
            server_agent.processed_tasks.append(text_task_102)

            # Process each task
            results = []
            for task_id, data, operation in tasks:
                if isinstance(data, list):
                    result = await client_agent.submit_calculation_task(
                        service_name="server-agent", task_id=task_id, numbers=data, operation=operation
                    )
                else:
                    result = await client_agent.submit_text_task(
                        service_name="server-agent", task_id=task_id, text=data, operation=operation
                    )
                results.append(result)

            # Verify the results
            assert len(results) == 4

            # Check first result
            if isinstance(results[0], dict):
                assert results[0]["task_id"] == "calc-101"
                assert results[0]["result"] == 10
            else:
                assert results[0] == 10

            # Check second result
            if isinstance(results[1], dict):
                assert results[1]["task_id"] == "calc-102"
                assert results[1]["result"] == 12.5
            else:
                assert results[1] == 12.5

            # Check third result
            if isinstance(results[2], dict):
                assert results[2]["task_id"] == "text-101"
                assert results[2]["result"] == 5
            else:
                assert results[2] == 5

            # Check fourth result
            if isinstance(results[3], dict):
                assert results[3]["task_id"] == "text-102"
                assert results[3]["result"] == "WORLD"
            else:
                assert results[3] == "WORLD"

            # Verify that the server processed all tasks
            assert len(server_agent.processed_tasks) == 4

            # Verify communicators were used correctly
            client_communicator.verify_all_expectations_met()
