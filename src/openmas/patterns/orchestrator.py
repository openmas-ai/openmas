"""Orchestrator-Worker pattern helpers for OpenMAS.

This module provides helper classes for implementing the Orchestrator-Worker pattern
in a multi-agent system. The pattern consists of:

1. An orchestrator agent that coordinates a workflow by delegating tasks to worker agents
2. Worker agents that specialize in specific tasks and report results back to the orchestrator
3. A communication mechanism for task delegation and result aggregation

This pattern is useful for decomposing complex workflows into modular components that
can be executed by specialized agents, potentially in parallel.
"""

import asyncio
import uuid
from typing import Any, Callable, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from openmas.agent.base import BaseAgent
from openmas.logging import get_logger

logger = get_logger(__name__)


class TaskRequest(BaseModel):
    """A task request sent from an orchestrator to a worker."""

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """A task result sent from a worker to an orchestrator."""

    task_id: str
    status: str  # "success", "failure", "in_progress"
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkerInfo(BaseModel):
    """Information about a worker agent."""

    name: str
    capabilities: Set[str] = Field(default_factory=set)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseOrchestratorAgent(BaseAgent):
    """Base orchestrator agent for coordinating tasks among worker agents.

    The orchestrator is responsible for:
    1. Managing the workflow of complex tasks
    2. Discovering and tracking available worker agents
    3. Delegating subtasks to appropriate worker agents
    4. Aggregating results from workers
    5. Handling failures and retries
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the orchestrator agent."""
        super().__init__(*args, **kwargs)

        # Dictionary mapping worker names to their capabilities
        self._workers: Dict[str, WorkerInfo] = {}

        # Dictionary mapping task IDs to their status and metadata
        self._tasks: Dict[str, Dict[str, Any]] = {}

        # Default timeout for worker responses
        self.default_timeout = 60.0

    async def setup(self) -> None:
        """Set up the orchestrator agent.

        Registers handlers for worker registration and task results.
        """
        await self.communicator.register_handler("register_worker", self._handle_worker_registration)
        await self.communicator.register_handler("task_result", self._handle_task_result)

    async def _handle_worker_registration(self, worker_info: Dict[str, Any]) -> Dict[str, Any]:
        """Handle worker registration requests.

        Args:
            worker_info: Information about the worker, including name and capabilities

        Returns:
            Registration confirmation
        """
        worker = WorkerInfo(**worker_info)
        self._workers[worker.name] = worker

        self.logger.info("Worker registered", worker_name=worker.name, capabilities=list(worker.capabilities))

        return {"status": "registered", "orchestrator": self.name}

    async def _handle_task_result(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle task results from workers.

        Args:
            result_data: The task result data from a worker

        Returns:
            Result acknowledgment
        """
        result = TaskResult(**result_data)

        if result.task_id not in self._tasks:
            self.logger.warning("Received result for unknown task", task_id=result.task_id)
            return {"status": "unknown_task"}

        task_info = self._tasks[result.task_id]
        task_info["status"] = result.status
        task_info["result"] = result.result
        task_info["completed_at"] = asyncio.get_event_loop().time()

        # Call the result callback if one was registered
        if "callback" in task_info and callable(task_info["callback"]):
            await task_info["callback"](result)

        self.logger.debug("Task result received", task_id=result.task_id, status=result.status)

        return {"status": "acknowledged"}

    async def discover_workers(self) -> List[WorkerInfo]:
        """Discover available worker agents.

        This method broadcasts a discovery message to find workers.

        Returns:
            List of discovered worker information
        """
        # Broadcast discovery message
        try:
            response = await self.communicator.send_request(
                target_service="broadcast",
                method="discover_workers",
                params={"orchestrator": self.name},
                timeout=5.0,
            )

            # Process responses
            for worker_data in response.get("workers", []):
                if isinstance(worker_data, dict) and "name" in worker_data:
                    worker = WorkerInfo(**worker_data)
                    self._workers[worker.name] = worker

            self.logger.info("Workers discovered", worker_count=len(self._workers), workers=list(self._workers.keys()))

        except Exception as e:
            self.logger.error("Error discovering workers", error=str(e))

        return list(self._workers.values())

    def find_worker_for_task(self, task_type: str) -> Optional[str]:
        """Find a suitable worker for a given task type.

        Args:
            task_type: The type of task to find a worker for

        Returns:
            The name of a suitable worker, or None if no worker is found
        """
        for name, info in self._workers.items():
            if task_type in info.capabilities:
                return name
        return None

    async def delegate_task(
        self,
        worker_name: str,
        task_type: str,
        parameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        callback: Optional[Callable[[TaskResult], Any]] = None,
    ) -> str:
        """Delegate a task to a worker agent.

        Args:
            worker_name: The name of the worker to delegate to
            task_type: The type of task to delegate
            parameters: Parameters for the task
            metadata: Additional metadata for the task
            timeout: Timeout for the task in seconds
            callback: Callback function to call when the task completes

        Returns:
            The ID of the delegated task

        Raises:
            ValueError: If the worker is not registered
        """
        if worker_name not in self._workers:
            raise ValueError(f"Worker '{worker_name}' is not registered")

        # Create the task request
        task_request = TaskRequest(task_type=task_type, parameters=parameters or {}, metadata=metadata or {})

        # Store task information
        self._tasks[task_request.task_id] = {
            "worker": worker_name,
            "task_type": task_type,
            "status": "pending",
            "created_at": asyncio.get_event_loop().time(),
            "timeout": timeout or self.default_timeout,
            "callback": callback,
        }

        # Send the task to the worker
        await self.communicator.send_notification(
            target_service=worker_name, method="execute_task", params=task_request.model_dump()
        )

        self.logger.debug("Task delegated", task_id=task_request.task_id, worker=worker_name, task_type=task_type)

        return task_request.task_id

    async def get_task_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[TaskResult]:
        """Get the result of a task.

        Args:
            task_id: The ID of the task
            timeout: How long to wait for the result in seconds

        Returns:
            The task result, or None if the task is not found or times out
        """
        if task_id not in self._tasks:
            return None

        task_info = self._tasks[task_id]

        # If the task is already completed, return the result
        if task_info["status"] in ("success", "failure"):
            return TaskResult(
                task_id=task_id,
                status=task_info["status"],
                result=task_info.get("result"),
                error=task_info.get("error"),
            )

        # Wait for the result with timeout
        timeout_value = timeout or task_info["timeout"]
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < timeout_value:
            # Check if the task has completed
            if task_info["status"] in ("success", "failure"):
                return TaskResult(
                    task_id=task_id,
                    status=task_info["status"],
                    result=task_info.get("result"),
                    error=task_info.get("error"),
                )

            # Wait a bit before checking again
            await asyncio.sleep(0.1)

        # Timeout occurred
        return TaskResult(task_id=task_id, status="timeout", error="Task timed out")

    async def orchestrate_workflow(
        self, tasks: List[Dict[str, Any]], parallel: bool = False
    ) -> Dict[int, Dict[str, Any]]:
        """Orchestrate a workflow of multiple tasks.

        Args:
            tasks: List of task definitions, each containing:
                - task_type: The type of task
                - parameters: Parameters for the task (optional)
                - worker: Specific worker to use (optional)
            parallel: Whether to execute tasks in parallel

        Returns:
            Dictionary mapping task positions or IDs to results
        """
        results: Dict[int, Dict[str, Any]] = {}

        if parallel:
            # Execute tasks in parallel
            task_futures = []
            for i, task_def in enumerate(tasks):
                worker = task_def.get("worker") or self.find_worker_for_task(task_def["task_type"])
                if not worker:
                    results[i] = {
                        "status": "failure",
                        "error": f"No worker found for task type: {task_def['task_type']}",
                    }
                    continue

                task_id = await self.delegate_task(
                    worker_name=worker, task_type=task_def["task_type"], parameters=task_def.get("parameters", {})
                )

                # Create a future for this task result
                task_futures.append((i, task_id))

            # Wait for all task results
            for i, task_id in task_futures:
                result = await self.get_task_result(task_id)
                results[i] = (
                    result.model_dump() if result else {"status": "failure", "error": "Failed to get task result"}
                )
        else:
            # Execute tasks sequentially
            for i, task_def in enumerate(tasks):
                worker = task_def.get("worker") or self.find_worker_for_task(task_def["task_type"])
                if not worker:
                    results[i] = {
                        "status": "failure",
                        "error": f"No worker found for task type: {task_def['task_type']}",
                    }
                    continue

                # Add results from previous tasks if requested
                parameters = task_def.get("parameters", {}).copy()
                if task_def.get("include_previous_results", False):
                    parameters["previous_results"] = results

                task_id = await self.delegate_task(
                    worker_name=worker, task_type=task_def["task_type"], parameters=parameters
                )

                result = await self.get_task_result(task_id)
                results[i] = (
                    result.model_dump() if result else {"status": "failure", "error": "Failed to get task result"}
                )

                # Stop the workflow if a task fails and abort_on_failure is set
                if (result is None or result.status != "success") and task_def.get("abort_on_failure", False):
                    break

        return results


class TaskHandler:
    """A decorator for registering task handlers in worker agents."""

    def __init__(self, task_type: str, description: str = ""):
        """Initialize the task handler decorator.

        Args:
            task_type: The type of task this handler can process
            description: A description of the task handler
        """
        self.task_type = task_type
        self.description = description

    def __call__(self, func: Callable) -> Callable:
        """Decorate a method as a task handler.

        Args:
            func: The method to decorate

        Returns:
            The decorated method
        """
        setattr(func, "_task_handler", {"task_type": self.task_type, "description": self.description})
        return func


class BaseWorkerAgent(BaseAgent):
    """Base worker agent for processing specialized tasks.

    Workers register with orchestrators, receive task assignments,
    process them according to their capabilities, and return results.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the worker agent."""
        super().__init__(*args, **kwargs)

        # Dictionary mapping task types to handler methods
        self._task_handlers: Dict[str, Callable] = {}

        # Set of orchestrators this worker is registered with
        self._orchestrators: Set[str] = set()

        # Dict of active tasks being processed
        self._active_tasks: Dict[str, Dict[str, Any]] = {}

    async def setup(self) -> None:
        """Set up the worker agent.

        Discovers and registers task handlers, registers with orchestrators,
        and sets up communication handlers.
        """
        # Discover task handlers from class methods
        self._discover_task_handlers()

        # Register handler for executing tasks
        await self.communicator.register_handler("execute_task", self._handle_execute_task)

        # Register handler for discovery requests
        await self.communicator.register_handler("discover_workers", self._handle_discovery)

    def _discover_task_handlers(self) -> None:
        """Discover task handlers from class methods."""
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if callable(attr) and hasattr(attr, "_task_handler"):
                task_info = getattr(attr, "_task_handler")
                if isinstance(task_info, dict) and "task_type" in task_info:
                    self._task_handlers[task_info["task_type"]] = attr
                    self.logger.debug("Registered task handler", task_type=task_info["task_type"], handler=attr_name)

    async def register_with_orchestrator(self, orchestrator_name: str) -> bool:
        """Register this worker with an orchestrator.

        Args:
            orchestrator_name: The name of the orchestrator to register with

        Returns:
            True if registration was successful, False otherwise
        """
        try:
            response = await self.communicator.send_request(
                target_service=orchestrator_name,
                method="register_worker",
                params={
                    "name": self.name,
                    "capabilities": list(self._task_handlers.keys()),
                    "metadata": {"agent_type": self.__class__.__name__},
                },
            )

            if response.get("status") == "registered":
                self._orchestrators.add(orchestrator_name)
                self.logger.info("Registered with orchestrator", orchestrator=orchestrator_name)
                return True

            self.logger.warning(
                "Failed to register with orchestrator", orchestrator=orchestrator_name, response=response
            )
            return False

        except Exception as e:
            self.logger.error("Error registering with orchestrator", orchestrator=orchestrator_name, error=str(e))
            return False

    async def _handle_discovery(self, discovery_request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle worker discovery requests from orchestrators.

        Args:
            discovery_request: The discovery request

        Returns:
            Worker information
        """
        orchestrator = discovery_request.get("orchestrator")
        if orchestrator and orchestrator not in self._orchestrators:
            self._orchestrators.add(orchestrator)
            self.logger.info("Added orchestrator from discovery", orchestrator=orchestrator)

        return {
            "name": self.name,
            "capabilities": list(self._task_handlers.keys()),
            "metadata": {"agent_type": self.__class__.__name__},
        }

    async def _handle_execute_task(self, task_request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a task execution request from an orchestrator.

        Args:
            task_request_data: The task request data

        Returns:
            Acknowledgment of the task request
        """
        task_request = TaskRequest(**task_request_data)

        # Check if we have a handler for this task type
        if task_request.task_type not in self._task_handlers:
            self.logger.warning(
                "Received task with no handler", task_id=task_request.task_id, task_type=task_request.task_type
            )

            # Send failure result back to the orchestrator
            await self._send_task_result(
                task_id=task_request.task_id,
                status="failure",
                error=f"No handler for task type: {task_request.task_type}",
            )
            return {"status": "rejected", "reason": "no_handler"}

        # Store the task in active tasks
        self._active_tasks[task_request.task_id] = {
            "task_type": task_request.task_type,
            "parameters": task_request.parameters,
            "metadata": task_request.metadata,
            "status": "in_progress",
            "started_at": asyncio.get_event_loop().time(),
        }

        # Execute the task in the background
        asyncio.create_task(self._execute_task(task_request))

        return {"status": "accepted"}

    async def _execute_task(self, task_request: TaskRequest) -> None:
        """Execute a task in the background.

        Args:
            task_request: The task request to execute
        """
        handler = self._task_handlers[task_request.task_type]

        try:
            # Execute the handler
            result = await handler(**task_request.parameters)

            # Send success result
            await self._send_task_result(task_id=task_request.task_id, status="success", result=result)

        except Exception as e:
            self.logger.exception(
                "Error executing task", task_id=task_request.task_id, task_type=task_request.task_type, error=str(e)
            )

            # Send failure result
            await self._send_task_result(task_id=task_request.task_id, status="failure", error=str(e))

        # Remove from active tasks
        if task_request.task_id in self._active_tasks:
            del self._active_tasks[task_request.task_id]

    async def _send_task_result(
        self, task_id: str, status: str, result: Any = None, error: Optional[str] = None
    ) -> None:
        """Send a task result back to the orchestrator.

        Args:
            task_id: The ID of the task
            status: The status of the task ("success", "failure")
            result: The result of the task
            error: Error message if the task failed
        """
        task_info = self._active_tasks.get(task_id, {})
        orchestrator = task_info.get("metadata", {}).get("orchestrator")

        # If we don't know which orchestrator to send to, send to all
        if not orchestrator:
            for orch in self._orchestrators:
                await self._send_result_to_orchestrator(
                    orchestrator=orch, task_id=task_id, status=status, result=result, error=error
                )
        else:
            await self._send_result_to_orchestrator(
                orchestrator=orchestrator, task_id=task_id, status=status, result=result, error=error
            )

    async def _send_result_to_orchestrator(
        self, orchestrator: str, task_id: str, status: str, result: Any = None, error: Optional[str] = None
    ) -> None:
        """Send a task result to a specific orchestrator.

        Args:
            orchestrator: The name of the orchestrator
            task_id: The ID of the task
            status: The status of the task
            result: The result of the task
            error: Error message if the task failed
        """
        task_result = TaskResult(
            task_id=task_id, status=status, result=result, error=error, metadata={"worker": self.name}
        )

        try:
            await self.communicator.send_notification(
                target_service=orchestrator, method="task_result", params=task_result.model_dump()
            )

            self.logger.debug("Sent task result", task_id=task_id, orchestrator=orchestrator, status=status)

        except Exception as e:
            self.logger.error("Error sending task result", task_id=task_id, orchestrator=orchestrator, error=str(e))


# Example usage of the Orchestrator-Worker pattern


class DataProcessingWorker(BaseWorkerAgent):
    """Example worker agent for data processing tasks."""

    @TaskHandler(task_type="clean_data", description="Clean and validate input data")
    async def clean_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean and validate input data.

        Args:
            data: The data to clean

        Returns:
            The cleaned data
        """
        # Example implementation
        cleaned_data = []
        for item in data:
            # Remove null values
            clean_item = {k: v for k, v in item.items() if v is not None}
            cleaned_data.append(clean_item)
        return cleaned_data

    @TaskHandler(task_type="transform_data", description="Transform data structure")
    async def transform_data(self, data: List[Dict[str, Any]], format: str = "flat") -> List[Dict[str, Any]]:
        """Transform data structure.

        Args:
            data: The data to transform
            format: The target format ("flat", "nested")

        Returns:
            The transformed data
        """
        # Example implementation
        if format == "flat":
            return self._flatten_data(data)
        elif format == "nested":
            return self._nest_data(data)
        return data

    def _flatten_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Flatten nested data structures."""
        # Implementation details omitted
        return data

    def _nest_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create nested data structures."""
        # Implementation details omitted
        return data


class AnalysisWorker(BaseWorkerAgent):
    """Example worker agent for data analysis tasks."""

    @TaskHandler(task_type="calculate_statistics", description="Calculate statistical metrics")
    async def calculate_statistics(self, data: List[Dict[str, Any]], fields: List[str]) -> Dict[str, Any]:
        """Calculate statistical metrics for the specified fields.

        Args:
            data: The data to analyze
            fields: The fields to calculate statistics for

        Returns:
            Dictionary of statistics by field
        """
        # Example implementation
        result = {}

        for field in fields:
            values = [item.get(field, 0) for item in data if field in item]
            if not values:
                continue

            result[field] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": sum(values) / len(values),
            }

        return result


class DataPipelineOrchestrator(BaseOrchestratorAgent):
    """Example orchestrator agent for a data processing pipeline."""

    async def process_data_pipeline(self, raw_data: List[Dict[str, Any]], analysis_fields: List[str]) -> Dict[str, Any]:
        """Process a complete data pipeline.

        Args:
            raw_data: The raw data to process
            analysis_fields: Fields to analyze

        Returns:
            The pipeline results including processed data and analysis
        """
        # Orchestrate a multi-step workflow
        workflow: List[Dict[str, Any]] = [
            {"task_type": "clean_data", "parameters": {"data": raw_data}},
            {
                "task_type": "transform_data",
                "parameters": {"format": "flat"},
                "include_previous_results": True,
                "abort_on_failure": True,
            },
            {
                "task_type": "calculate_statistics",
                "parameters": {"fields": analysis_fields},
                "include_previous_results": True,
            },
        ]

        results = await self.orchestrate_workflow(workflow)

        # Combine all results into a final output
        final_result = {
            "cleaned_data": results.get(0, {}).get("result", []),
            "transformed_data": results.get(1, {}).get("result", []),
            "statistics": results.get(2, {}).get("result", {}),
        }

        return final_result


# Example of how to use the pattern:
"""
async def main():
    # Create orchestrator
    orchestrator = DataPipelineOrchestrator(name="data_pipeline_orchestrator")
    await orchestrator.start()

    # Create workers
    data_worker = DataProcessingWorker(name="data_processor")
    analysis_worker = AnalysisWorker(name="data_analyzer")

    await data_worker.start()
    await analysis_worker.start()

    # Register workers with orchestrator
    await data_worker.register_with_orchestrator(orchestrator.name)
    await analysis_worker.register_with_orchestrator(orchestrator.name)

    # Alternatively, discover workers
    await orchestrator.discover_workers()

    # Process a data pipeline
    raw_data = [
        {"id": 1, "value": 42, "label": "A"},
        {"id": 2, "value": 18, "label": "B"},
        {"id": 3, "value": 73, "label": "C"}
    ]

    result = await orchestrator.process_data_pipeline(
        raw_data=raw_data,
        analysis_fields=["value"]
    )

    print(f"Pipeline result: {result}")

    # Clean up
    await data_worker.stop()
    await analysis_worker.stop()
    await orchestrator.stop()

# Run the example
if __name__ == "__main__":
    asyncio.run(main())
"""
