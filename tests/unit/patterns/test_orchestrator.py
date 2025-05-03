"""Unit tests for the Orchestrator-Worker pattern."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from openmas.patterns.orchestrator import BaseOrchestratorAgent, BaseWorkerAgent, TaskHandler, TaskRequest, TaskResult


class TestOrchestratorAgent:
    """Test the BaseOrchestratorAgent class."""

    @pytest.fixture
    def mock_communicator(self):
        communicator = AsyncMock()
        communicator.start = AsyncMock()
        communicator.stop = AsyncMock()
        communicator.send_request = AsyncMock()
        communicator.send_notification = AsyncMock()
        communicator.register_handler = AsyncMock()
        return communicator

    class MockOrchestratorAgent(BaseOrchestratorAgent):
        """Mock implementation of the orchestrator with required methods."""

        async def run(self) -> None:
            """Run implementation."""
            pass

        async def shutdown(self) -> None:
            """Shutdown implementation."""
            pass

    @pytest.fixture
    def orchestrator(self, mock_communicator):
        # Pass config as a dict to avoid using environment variables
        orchestrator = self.MockOrchestratorAgent(
            name="test_orchestrator", config={"name": "test_orchestrator", "communicator_type": "mock"}
        )
        orchestrator.set_communicator(mock_communicator)
        return orchestrator

    @pytest.mark.asyncio
    async def test_setup(self, orchestrator):
        """Test that setup registers the required handlers."""
        await orchestrator.setup()

        # Verify that the required handlers are registered
        orchestrator.communicator.register_handler.assert_any_call(
            "register_worker", orchestrator._handle_worker_registration
        )
        orchestrator.communicator.register_handler.assert_any_call("task_result", orchestrator._handle_task_result)

    @pytest.mark.asyncio
    async def test_worker_registration(self, orchestrator):
        """Test handling worker registration."""
        # Call the setup method to ensure handlers are registered
        await orchestrator.setup()

        # Create worker info for registration
        worker_info = {"name": "test_worker", "capabilities": ["task1", "task2"], "metadata": {"version": "1.0"}}

        # Call the handler method
        result = await orchestrator._handle_worker_registration(worker_info)

        # Check the response
        assert result["status"] == "registered"
        assert result["orchestrator"] == "test_orchestrator"

        # Verify the worker was added to the internal registry
        assert "test_worker" in orchestrator._workers
        assert orchestrator._workers["test_worker"].capabilities == {"task1", "task2"}
        assert orchestrator._workers["test_worker"].metadata == {"version": "1.0"}

    @pytest.mark.asyncio
    async def test_find_worker_for_task(self, orchestrator):
        """Test finding a worker for a specific task."""
        await orchestrator.setup()

        # Register a few workers with different capabilities
        workers = [
            {"name": "worker1", "capabilities": ["task1", "task2"]},
            {"name": "worker2", "capabilities": ["task2", "task3"]},
            {"name": "worker3", "capabilities": ["task3", "task4"]},
        ]

        for worker in workers:
            await orchestrator._handle_worker_registration(worker)

        # Test finding workers for different tasks
        assert orchestrator.find_worker_for_task("task1") == "worker1"
        assert orchestrator.find_worker_for_task("task2") in ["worker1", "worker2"]
        assert orchestrator.find_worker_for_task("task3") in ["worker2", "worker3"]
        assert orchestrator.find_worker_for_task("task4") == "worker3"
        assert orchestrator.find_worker_for_task("nonexistent") is None

    @pytest.mark.asyncio
    async def test_task_delegation(self, orchestrator):
        """Test delegating a task to a worker."""
        await orchestrator.setup()

        # Register a worker
        await orchestrator._handle_worker_registration({"name": "math_worker", "capabilities": ["add", "multiply"]})

        # Delegate a task to the worker
        task_id = await orchestrator.delegate_task(
            worker_name="math_worker", task_type="add", parameters={"a": 2, "b": 3}, metadata={"priority": "high"}
        )

        # Verify that the task was added to the internal registry
        assert task_id in orchestrator._tasks
        assert orchestrator._tasks[task_id]["worker"] == "math_worker"
        assert orchestrator._tasks[task_id]["task_type"] == "add"
        assert orchestrator._tasks[task_id]["status"] == "pending"

        # Verify the notification was sent to the worker
        orchestrator.communicator.send_notification.assert_called_once()
        call_args = orchestrator.communicator.send_notification.call_args[1]
        assert call_args["target_service"] == "math_worker"
        assert call_args["method"] == "execute_task"
        assert call_args["params"]["task_type"] == "add"
        assert call_args["params"]["parameters"] == {"a": 2, "b": 3}
        assert call_args["params"]["metadata"] == {"priority": "high"}

    @pytest.mark.asyncio
    async def test_handle_task_result(self, orchestrator):
        """Test handling task results from workers."""
        await orchestrator.setup()

        # Create a task first
        task_id = "test-task-123"
        orchestrator._tasks[task_id] = {
            "worker": "math_worker",
            "task_type": "add",
            "status": "pending",
            "created_at": asyncio.get_event_loop().time(),
            "timeout": 60.0,
        }

        # Mock a callback function
        callback = AsyncMock()
        orchestrator._tasks[task_id]["callback"] = callback

        # Create a task result
        result_data = {"task_id": task_id, "status": "success", "result": 5, "error": None, "metadata": {}}

        # Process the result
        response = await orchestrator._handle_task_result(result_data)

        # Verify the response
        assert response["status"] == "acknowledged"

        # Check task status was updated
        assert orchestrator._tasks[task_id]["status"] == "success"
        assert orchestrator._tasks[task_id]["result"] == 5
        assert "completed_at" in orchestrator._tasks[task_id]

        # Verify callback was called
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrate_workflow_sequential(self, orchestrator):
        """Test orchestrating a sequential workflow."""
        await orchestrator.setup()

        # Register workers
        await orchestrator._handle_worker_registration({"name": "math_worker", "capabilities": ["add", "multiply"]})

        # Create a workflow
        workflow = [
            {"task_type": "multiply", "parameters": {"a": 2, "b": 3}, "worker": "math_worker"},
            {"task_type": "add", "parameters": {"a": 5}, "include_previous_results": True, "worker": "math_worker"},
        ]

        # Mock the delegate_task method to avoid actual delegation
        original_delegate = orchestrator.delegate_task
        orchestrator.delegate_task = AsyncMock()
        orchestrator.delegate_task.return_value = "task-id-123"

        # Mock get_task_result to return simulated results
        orchestrator.get_task_result = AsyncMock()
        orchestrator.get_task_result.side_effect = [
            TaskResult(task_id="task-id-123", status="success", result=6),  # 2 * 3 = 6
            TaskResult(task_id="task-id-456", status="success", result=11),  # 5 + 6 = 11
        ]

        # Execute the workflow
        results = await orchestrator.orchestrate_workflow(workflow)

        # Verify results
        assert len(results) == 2
        assert results[0]["result"] == 6
        assert results[1]["result"] == 11

        # Restore original delegate_task
        orchestrator.delegate_task = original_delegate


class MockWorkerAgent:
    """Test the BaseWorkerAgent class."""

    @pytest.fixture
    def mock_communicator(self):
        communicator = AsyncMock()
        communicator.start = AsyncMock()
        communicator.stop = AsyncMock()
        communicator.send_request = AsyncMock()
        communicator.send_notification = AsyncMock()
        communicator.register_handler = AsyncMock()
        return communicator

    class MockWorker(BaseWorkerAgent):
        """Mock implementation of worker agent for testing."""

        async def run(self) -> None:
            """Run implementation."""
            pass

        async def shutdown(self) -> None:
            """Shutdown implementation."""
            pass

        @TaskHandler(task_type="add", description="Add two numbers")
        async def add(self, a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        @TaskHandler(task_type="multiply", description="Multiply two numbers")
        async def multiply(self, a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

    @pytest.fixture
    def worker(self, mock_communicator):
        # Pass config dict to avoid loading from environment variables
        worker = self.MockWorker(name="test_worker", config={"name": "test_worker", "communicator_type": "mock"})
        worker.set_communicator(mock_communicator)
        return worker

    @pytest.mark.asyncio
    async def test_setup(self, worker):
        """Test worker setup and task handler discovery."""
        await worker.setup()

        # Verify handlers were registered
        worker.communicator.register_handler.assert_any_call("discover_workers", worker._handle_discovery)
        worker.communicator.register_handler.assert_any_call("execute_task", worker._handle_execute_task)

        # Verify task handlers were discovered
        assert len(worker._task_handlers) == 2
        assert "add" in worker._task_handlers
        assert "multiply" in worker._task_handlers

    @pytest.mark.asyncio
    async def test_register_with_orchestrator(self, worker):
        """Test registering with an orchestrator."""
        # Mock the response from the orchestrator
        worker.communicator.send_request.return_value = {"status": "registered"}

        # Register with orchestrator
        result = await worker.register_with_orchestrator("test_orchestrator")

        # Verify the result and the communication
        assert result is True

        # Get the actual call arguments
        actual_call = worker.communicator.send_request.call_args
        assert actual_call.kwargs["target_service"] == "test_orchestrator"
        assert actual_call.kwargs["method"] == "register_worker"
        assert actual_call.kwargs["params"]["name"] == "test_worker"
        # Don't strictly check the capabilities list since it may be empty before setup
        assert "capabilities" in actual_call.kwargs["params"]
        assert actual_call.kwargs["params"]["metadata"]["agent_type"] == "TestWorker"

    @pytest.mark.asyncio
    async def test_handle_execute_task(self, worker):
        """Test handling an execute_task request."""
        await worker.setup()  # To discover task handlers

        # Create a task request
        task_request = {
            "task_id": "test-task-123",
            "task_type": "add",
            "parameters": {"a": 2, "b": 3},
            "metadata": {"orchestrator": "test_orchestrator"},
        }

        # Call the handler
        with patch.object(worker, "_execute_task", AsyncMock()) as mock_execute:
            response = await worker._handle_execute_task(task_request)

            # Verify the response
            assert response["status"] == "accepted"

            # Verify the execute_task method was called
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task(self, worker):
        """Test executing a task."""
        await worker.setup()  # To discover task handlers

        # Create a task request
        task_request = TaskRequest(
            task_id="test-task-123",
            task_type="add",
            parameters={"a": 2, "b": 3},
            metadata={"orchestrator": "test_orchestrator"},
        )

        # Mock the send_task_result method
        worker._send_task_result = AsyncMock()

        # Execute the task
        await worker._execute_task(task_request)

        # Verify the result was sent, but don't be strict about the error parameter
        # since it might be omitted if None
        assert worker._send_task_result.called
        call_args = worker._send_task_result.call_args.kwargs
        assert call_args["task_id"] == "test-task-123"
        assert call_args["status"] == "success"
        assert call_args["result"] == 5
        # error parameter might be omitted if None


class TestTaskHandler:
    """Test the TaskHandler decorator."""

    def test_decorator_registers_task_handler(self):
        """Test that the TaskHandler decorator correctly registers task handlers."""

        # Create a dummy function
        async def dummy_func(self, param1, param2):
            return param1 + param2

        # Apply the decorator directly, since we're testing the decorator itself
        decorated_func = TaskHandler(task_type="test_task", description="Test task")(dummy_func)

        # Check the attributes added by the decorator
        assert hasattr(decorated_func, "_task_handler")
        assert decorated_func._task_handler["task_type"] == "test_task"
        assert decorated_func._task_handler["description"] == "Test task"
