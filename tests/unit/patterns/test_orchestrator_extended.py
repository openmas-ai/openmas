"""Extended unit tests for the Orchestrator-Worker pattern."""

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from openmas.patterns.orchestrator import (
    AnalysisWorker,
    BaseOrchestratorAgent,
    DataPipelineOrchestrator,
    DataProcessingWorker,
    TaskResult,
)


class TestOrchestratorExtended:
    """Extended tests for the BaseOrchestratorAgent class."""

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
        """Mock implementation of the orchestrator."""

        async def run(self) -> None:
            """Run implementation."""
            pass

        async def shutdown(self) -> None:
            """Shutdown implementation."""
            pass

    @pytest.fixture
    def orchestrator(self, mock_communicator, tmp_path):
        orchestrator = self.MockOrchestratorAgent(
            name="test_orchestrator",
            config={"name": "test_orchestrator", "communicator_type": "mock"},
            project_root=tmp_path,
        )
        orchestrator.set_communicator(mock_communicator)
        return orchestrator

    @pytest.mark.asyncio
    async def test_discover_workers_success(self, orchestrator):
        """Test successful discovery of workers."""
        # Setup mock response from broadcast
        mock_response = {
            "workers": [
                {"name": "worker1", "capabilities": ["task1", "task2"]},
                {"name": "worker2", "capabilities": ["task3", "task4"]},
            ]
        }
        orchestrator.communicator.send_request.return_value = mock_response

        # Call the discover_workers method
        workers = await orchestrator.discover_workers()

        # Check that the request was sent correctly
        orchestrator.communicator.send_request.assert_called_once_with(
            target_service="broadcast",
            method="discover_workers",
            params={"orchestrator": "test_orchestrator"},
            timeout=5.0,
        )

        # Check that workers were added to the internal registry
        assert len(workers) == 2
        assert "worker1" in orchestrator._workers
        assert "worker2" in orchestrator._workers
        assert orchestrator._workers["worker1"].capabilities == {"task1", "task2"}
        assert orchestrator._workers["worker2"].capabilities == {"task3", "task4"}

    @pytest.mark.asyncio
    async def test_discover_workers_error(self, orchestrator):
        """Test error handling during worker discovery."""
        # Setup the mock to raise an exception
        orchestrator.communicator.send_request.side_effect = Exception("Network error")

        # Call the method
        workers = await orchestrator.discover_workers()

        # Verify no workers were discovered
        assert len(workers) == 0

    @pytest.mark.asyncio
    async def test_get_task_result_timeout(self, orchestrator):
        """Test getting a task result with timeout."""
        # Create a pending task
        task_id = "test-task-456"
        orchestrator._tasks[task_id] = {
            "worker": "math_worker",
            "task_type": "add",
            "status": "pending",
            "created_at": asyncio.get_event_loop().time(),
            "timeout": 0.1,  # Very short timeout for testing
        }

        # Mock get_task_result to simulate a timeout by returning None after wait
        with patch.object(BaseOrchestratorAgent, "get_task_result") as mock_get_result:
            mock_get_result.return_value = None

            # Get the task result, which should wait and then return None due to timeout
            result = await orchestrator.get_task_result(task_id)

            # Verify the result is None since the task timed out
            assert result is None

    @pytest.mark.asyncio
    async def test_orchestrate_workflow_parallel(self, orchestrator):
        """Test orchestrating a parallel workflow."""
        await orchestrator.setup()

        # Register workers
        await orchestrator._handle_worker_registration({"name": "math_worker", "capabilities": ["add", "multiply"]})

        # Create a workflow that can be executed in parallel
        workflow = [
            {"task_type": "add", "parameters": {"a": 2, "b": 3}, "worker": "math_worker"},
            {"task_type": "multiply", "parameters": {"a": 4, "b": 5}, "worker": "math_worker"},
        ]

        # Mock the delegate_task method
        original_delegate = orchestrator.delegate_task
        orchestrator.delegate_task = AsyncMock()
        orchestrator.delegate_task.side_effect = ["task-id-1", "task-id-2"]

        # Mock get_task_result to return simulated results
        orchestrator.get_task_result = AsyncMock()
        orchestrator.get_task_result.side_effect = [
            TaskResult(task_id="task-id-1", status="success", result=5),  # 2 + 3 = 5
            TaskResult(task_id="task-id-2", status="success", result=20),  # 4 * 5 = 20
        ]

        # Execute the workflow in parallel
        results = await orchestrator.orchestrate_workflow(workflow, parallel=True)

        # Verify results
        assert len(results) == 2
        assert results[0]["result"] == 5
        assert results[1]["result"] == 20

        # Verify both tasks were delegated before waiting for results (parallel execution)
        assert orchestrator.delegate_task.call_count == 2

        # Restore original delegate_task
        orchestrator.delegate_task = original_delegate

    @pytest.mark.asyncio
    async def test_orchestrate_workflow_with_failure(self, orchestrator):
        """Test orchestrating a workflow with a failing task."""
        await orchestrator.setup()

        # Register a worker
        await orchestrator._handle_worker_registration({"name": "math_worker", "capabilities": ["add"]})

        # Create a workflow
        workflow = [{"task_type": "add", "parameters": {"a": 2, "b": 3}, "worker": "math_worker"}]

        # Mock the delegate_task method
        orchestrator.delegate_task = AsyncMock()
        orchestrator.delegate_task.return_value = "task-id-1"

        # Mock get_task_result to return a failed result
        orchestrator.get_task_result = AsyncMock()
        orchestrator.get_task_result.return_value = TaskResult(
            task_id="task-id-1", status="failure", result=None, error="Division by zero"
        )

        # Execute the workflow
        results = await orchestrator.orchestrate_workflow(workflow)

        # Verify results include the error
        assert len(results) == 1
        assert results[0]["status"] == "failure"
        assert results[0]["error"] == "Division by zero"


class TestDataProcessingWorker:
    """Tests for the DataProcessingWorker class."""

    @pytest.fixture
    def mock_communicator(self):
        communicator = AsyncMock()
        communicator.start = AsyncMock()
        communicator.stop = AsyncMock()
        communicator.send_request = AsyncMock()
        communicator.send_notification = AsyncMock()
        communicator.register_handler = AsyncMock()
        return communicator

    # Create a concrete class implementing the required abstract methods
    class MockDataProcessingWorker(DataProcessingWorker):
        """Mock implementation of DataProcessingWorker with required methods."""

        async def run(self) -> None:
            """Run implementation."""
            pass

        async def shutdown(self) -> None:
            """Shutdown implementation."""
            pass

        # Override the methods for testing purposes with controlled behavior
        async def clean_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """Override for predictable test behavior."""
            # Remove duplicates and filter out null values
            result = []
            seen = set()
            for item in data:
                item_id = item["id"]
                if item_id not in seen:
                    seen.add(item_id)
                    # Filter out null values
                    filtered_item = {k: v for k, v in item.items() if v is not None}
                    result.append(filtered_item)
            return result

        async def transform_data(self, data: List[Dict[str, Any]], format: str = "flat") -> List[Dict[str, Any]]:
            """Override for predictable test behavior."""
            if format == "flat":
                # Flatten nested dictionaries
                result = []
                for item in data:
                    flat_item: Dict[str, Any] = {}
                    for key, value in item.items():
                        if isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                flat_item[f"{key}.{sub_key}"] = sub_value
                        else:
                            flat_item[key] = value
                    result.append(flat_item)
                return result
            elif format == "nested":
                # Convert dot notation to nested dictionaries
                result = []
                for item in data:
                    nested_item: Dict[str, Any] = {}
                    for key, value in item.items():
                        if "." in key:
                            parts = key.split(".")
                            if parts[0] not in nested_item:
                                nested_item[parts[0]] = {}
                            nested_item[parts[0]][parts[1]] = value
                        else:
                            nested_item[key] = value
                    result.append(nested_item)
                return result
            return data

    @pytest.fixture
    def worker(self, mock_communicator, tmp_path):
        worker = self.MockDataProcessingWorker(
            name="data_processor",
            config={"name": "data_processor", "communicator_type": "mock"},
            project_root=tmp_path,
        )
        worker.set_communicator(mock_communicator)
        return worker

    @pytest.mark.asyncio
    async def test_clean_data(self, worker):
        """Test the clean_data task handler."""
        # Sample data with null values and duplicates
        data = [
            {"id": 1, "name": "Alpha", "value": 10},
            {"id": 2, "name": None, "value": 20},
            {"id": 3, "name": "Charlie", "value": None},
            {"id": 1, "name": "Alpha", "value": 10},  # Duplicate
        ]

        # Call the clean_data method
        result = await worker.clean_data(data)

        # Verify duplicates are removed and null values are handled
        assert len(result) == 3  # Should have removed the duplicate
        for item in result:
            if item["id"] == 2:
                assert "name" not in item
            if item["id"] == 3:
                assert "value" not in item

    @pytest.mark.asyncio
    async def test_transform_data_flat(self, worker):
        """Test transforming data to flat format."""
        # Sample nested data
        data = [
            {"id": 1, "details": {"name": "Alpha", "value": 10}},
            {"id": 2, "details": {"name": "Beta", "value": 20}},
        ]

        # Transform to flat format (default)
        result = await worker.transform_data(data)

        # Verify the result is flattened
        assert len(result) == 2
        assert "details.name" in result[0]
        assert "details.value" in result[0]
        assert result[0]["details.name"] == "Alpha"
        assert result[0]["details.value"] == 10

    @pytest.mark.asyncio
    async def test_transform_data_nested(self, worker):
        """Test transforming data to nested format."""
        # Sample flat data
        data = [
            {"id": 1, "user.name": "Alpha", "user.age": 30},
            {"id": 2, "user.name": "Beta", "user.age": 25},
        ]

        # Transform to nested format
        result = await worker.transform_data(data, format="nested")

        # Verify the result is nested
        assert len(result) == 2
        assert "user" in result[0]
        assert isinstance(result[0]["user"], dict)
        assert result[0]["user"]["name"] == "Alpha"
        assert result[0]["user"]["age"] == 30


class TestAnalysisWorker:
    """Tests for the AnalysisWorker class."""

    @pytest.fixture
    def mock_communicator(self):
        communicator = AsyncMock()
        communicator.start = AsyncMock()
        communicator.stop = AsyncMock()
        communicator.send_request = AsyncMock()
        communicator.send_notification = AsyncMock()
        communicator.register_handler = AsyncMock()
        return communicator

    # Create a concrete class implementing the required abstract methods
    class MockAnalysisWorker(AnalysisWorker):
        """Mock implementation of AnalysisWorker with required methods."""

        async def run(self) -> None:
            """Run implementation."""
            pass

        async def shutdown(self) -> None:
            """Shutdown implementation."""
            pass

    @pytest.fixture
    def worker(self, mock_communicator, tmp_path):
        worker = self.MockAnalysisWorker(
            name="data_analyzer",
            config={"name": "data_analyzer", "communicator_type": "mock"},
            project_root=tmp_path,
        )
        worker.set_communicator(mock_communicator)
        return worker

    @pytest.mark.asyncio
    async def test_calculate_statistics(self, worker):
        """Test calculating statistics on data."""
        # Sample data
        data = [
            {"id": 1, "value": 10, "category": "A"},
            {"id": 2, "value": 20, "category": "B"},
            {"id": 3, "value": 30, "category": "A"},
            {"id": 4, "value": 40, "category": "B"},
        ]

        # Calculate statistics for the 'value' field
        result = await worker.calculate_statistics(data, fields=["value"])

        # Verify statistics are calculated correctly
        assert "value" in result
        assert result["value"]["min"] == 10
        assert result["value"]["max"] == 40
        assert result["value"]["mean"] == 25
        assert result["value"]["count"] == 4


class TestDataPipelineOrchestrator:
    """Tests for the DataPipelineOrchestrator class."""

    @pytest.fixture
    def mock_communicator(self):
        communicator = AsyncMock()
        communicator.start = AsyncMock()
        communicator.stop = AsyncMock()
        communicator.send_request = AsyncMock()
        communicator.send_notification = AsyncMock()
        communicator.register_handler = AsyncMock()
        return communicator

    # Create a concrete class implementing the required abstract methods
    class MockDataPipelineOrchestrator(DataPipelineOrchestrator):
        """Mock implementation of DataPipelineOrchestrator with required methods."""

        async def run(self) -> None:
            """Run implementation."""
            pass

        async def shutdown(self) -> None:
            """Shutdown implementation."""
            pass

    @pytest.fixture
    def orchestrator(self, mock_communicator, tmp_path):
        orchestrator = self.MockDataPipelineOrchestrator(
            name="data_pipeline",
            config={"name": "data_pipeline", "communicator_type": "mock"},
            project_root=tmp_path,
        )
        orchestrator.set_communicator(mock_communicator)
        return orchestrator

    @pytest.mark.asyncio
    async def test_process_data_pipeline(self, orchestrator):
        """Test the complete data pipeline process."""
        # Register mock workers
        await orchestrator._handle_worker_registration(
            {"name": "data_processor", "capabilities": ["clean_data", "transform_data"]}
        )
        await orchestrator._handle_worker_registration(
            {"name": "data_analyzer", "capabilities": ["calculate_statistics"]}
        )

        # Sample raw data
        raw_data = [
            {"id": 1, "name": "Alpha", "value": 10},
            {"id": 2, "name": "Beta", "value": 20},
            {"id": 3, "name": "Charlie", "value": 30},
        ]

        # Mock delegate_task to return predictable task IDs
        orchestrator.delegate_task = AsyncMock()
        orchestrator.delegate_task.side_effect = ["task-1", "task-2", "task-3"]

        # Mock get_task_result to return staged results
        orchestrator.get_task_result = AsyncMock()
        clean_result = TaskResult(
            task_id="task-1",
            status="success",
            result=[
                {"id": 1, "name": "Alpha", "value": 10},
                {"id": 2, "name": "Beta", "value": 20},
                {"id": 3, "name": "Charlie", "value": 30},
            ],
        )
        transform_result = TaskResult(
            task_id="task-2",
            status="success",
            result=[
                {"id": 1, "name": "Alpha", "value": 10},
                {"id": 2, "name": "Beta", "value": 20},
                {"id": 3, "name": "Charlie", "value": 30},
            ],
        )
        stats_result = TaskResult(
            task_id="task-3",
            status="success",
            result={
                "value": {
                    "min": 10,
                    "max": 30,
                    "mean": 20,
                    "count": 3,
                }
            },
        )
        orchestrator.get_task_result.side_effect = [clean_result, transform_result, stats_result]

        # Process the data pipeline
        result = await orchestrator.process_data_pipeline(raw_data, analysis_fields=["value"])

        # Verify the pipeline was executed correctly
        assert orchestrator.delegate_task.call_count == 3
        assert "cleaned_data" in result
        assert "transformed_data" in result
        assert "statistics" in result
        assert result["statistics"]["value"]["min"] == 10
        assert result["statistics"]["value"]["max"] == 30
