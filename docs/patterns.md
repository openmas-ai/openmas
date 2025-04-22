# Common Patterns in SimpleMas

This document describes common patterns and best practices for building multi-agent systems with SimpleMas.

## Basic Patterns

### Request-Response

The most common pattern is request-response:

```python
# Agent 1 sends a request
response = await agent1.send_request(
    target_service="agent2",
    method="get_data",
    params={"query": "weather"}
)

# Agent 2 handles the request
@agent2.handler("get_data")
async def handle_get_data(params):
    query = params.get("query")
    # Process the query
    return {"result": f"Data for {query}"}
```

### Notification

For one-way communication without expecting a response:

```python
# Agent 1 sends a notification
await agent1.send_notification(
    target_service="agent2",
    method="log_event",
    params={"event": "system_started"}
)

# Agent 2 handles the notification
@agent2.handler("log_event")
async def handle_log_event(params):
    event = params.get("event")
    # Process the event, no return value needed
```

## Advanced Patterns

### Pub-Sub Pattern

Implementing a publish-subscribe pattern:

```python
# Publisher agent
@publisher_agent.handler("subscribe")
async def handle_subscribe(params):
    topic = params.get("topic")
    subscriber = params.get("subscriber")
    # Add subscriber to topic
    return {"status": "subscribed"}

# Publisher sends updates
async def publish_update(topic, data):
    for subscriber in get_subscribers(topic):
        await publisher_agent.send_notification(
            target_service=subscriber,
            method="update",
            params={"topic": topic, "data": data}
        )

# Subscriber agent
@subscriber_agent.handler("update")
async def handle_update(params):
    topic = params.get("topic")
    data = params.get("data")
    # Process the update
```

### Service Discovery

Implementing dynamic service discovery:

```python
# Registry agent
@registry_agent.handler("register")
async def handle_register(params):
    service_name = params.get("service_name")
    service_url = params.get("service_url")
    # Register the service
    return {"status": "registered"}

@registry_agent.handler("discover")
async def handle_discover(params):
    service_name = params.get("service_name")
    # Find the service
    return {"service_url": get_service_url(service_name)}
```

## Best Practices

1. **Error Handling**: Always handle communication errors in your agents
2. **Timeout Management**: Set appropriate timeouts for requests
3. **Resource Cleanup**: Make sure to call `agent.stop()` when shutting down
4. **Message Validation**: Use Pydantic models to validate message structures

# Patterns in SimpleMAS

SimpleMAS provides helper classes and utilities for implementing common patterns in multi-agent systems.

## Orchestrator-Worker Pattern

The Orchestrator-Worker pattern is a powerful design pattern for coordinating complex workflows within a multi-agent system. It consists of:

1. **Orchestrator Agent**: A central coordinator that manages workflow execution by delegating tasks to specialized workers and aggregating their results.
2. **Worker Agents**: Specialized agents that perform specific tasks within their domain of expertise.
3. **Task Communication**: A standardized protocol for task delegation, status reporting, and result retrieval.

### Key Components

SimpleMAS implements the Orchestrator-Worker pattern with the following components:

- `BaseOrchestratorAgent`: Base class for implementing orchestrator agents
- `BaseWorkerAgent`: Base class for implementing worker agents
- `TaskHandler`: Decorator for registering task handlers in worker agents
- `TaskRequest` and `TaskResult`: Data models for task delegation and reporting

### Benefits

- **Separation of Concerns**: Workers focus on specific tasks while orchestrators manage workflow coordination
- **Scalability**: Adding new capabilities requires creating new worker agents without modifying existing code
- **Fault Tolerance**: Orchestrators can handle worker failures, timeouts, and retries
- **Parallelism**: Tasks can be executed concurrently when appropriate
- **Workflow Management**: Complex, multi-step processes can be coordinated centrally

### Example Usage

Below is a simple example of how to use the Orchestrator-Worker pattern in SimpleMAS:

```python
from simple_mas.patterns.orchestrator import (
    BaseOrchestratorAgent,
    BaseWorkerAgent,
    TaskHandler
)

# Define a worker agent with task handlers
class MathWorker(BaseWorkerAgent):
    @TaskHandler(task_type="add", description="Add two numbers")
    async def add(self, a: int, b: int) -> int:
        return a + b

    @TaskHandler(task_type="multiply", description="Multiply two numbers")
    async def multiply(self, a: int, b: int) -> int:
        return a * b

# Define an orchestrator agent
class CalculationOrchestrator(BaseOrchestratorAgent):
    async def calculate_expression(self, a: int, b: int, c: int) -> int:
        # Define a workflow
        workflow = [
            {
                "task_type": "multiply",
                "parameters": {"a": b, "b": c}
            },
            {
                "task_type": "add",
                "parameters": {"a": a},
                "include_previous_results": True,
                "abort_on_failure": True
            }
        ]

        # Execute the workflow
        results = await self.orchestrate_workflow(workflow)

        # Get the final result
        return results.get(1, {}).get("result", 0)

# Main application
async def main():
    # Create agents
    orchestrator = CalculationOrchestrator(name="calc_orchestrator")
    worker = MathWorker(name="math_worker")

    # Start agents
    await orchestrator.start()
    await worker.start()

    # Register worker with orchestrator
    await worker.register_with_orchestrator(orchestrator.name)

    # Calculate an expression: a + (b * c)
    result = await orchestrator.calculate_expression(5, 2, 3)
    print(f"Result: {result}")  # Should print "Result: 11"

    # Clean up
    await worker.stop()
    await orchestrator.stop()
```

### Implementing an Orchestrator Agent

To create an orchestrator agent:

1. Inherit from `BaseOrchestratorAgent`
2. Implement high-level workflow methods that use `orchestrate_workflow()`
3. Optionally override `setup()` to add additional initialization logic

```python
class MyOrchestrator(BaseOrchestratorAgent):
    async def setup(self) -> None:
        # Call parent setup to register standard handlers
        await super().setup()

        # Add custom initialization logic
        self.default_timeout = 30.0  # Set default timeout for tasks

    async def process_workflow(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # Define the workflow steps
        workflow = [
            {
                "task_type": "validate_input",
                "parameters": {"data": input_data}
            },
            {
                "task_type": "process_data",
                "include_previous_results": True
            },
            {
                "task_type": "generate_report",
                "include_previous_results": True
            }
        ]

        # Execute the workflow (sequential by default)
        results = await self.orchestrate_workflow(workflow)

        # Return the final result
        return results.get(2, {}).get("result", {})
```

#### Key Methods

- `discover_workers()`: Find available worker agents
- `delegate_task()`: Send a task to a specific worker
- `get_task_result()`: Get the result of a task (with optional timeout)
- `orchestrate_workflow()`: Execute a multi-step workflow (sequential or parallel)
- `find_worker_for_task()`: Find a suitable worker for a given task type

### Implementing a Worker Agent

To create a worker agent:

1. Inherit from `BaseWorkerAgent`
2. Define task handlers using the `@TaskHandler` decorator
3. Optionally override `setup()` to add additional initialization logic

```python
class MyWorker(BaseWorkerAgent):
    async def setup(self) -> None:
        # Call parent setup to register standard handlers
        await super().setup()

        # Initialize resources
        self.database = await Database.connect()

    @TaskHandler(task_type="process_data", description="Process data records")
    async def process_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Process the data
        processed_data = []
        for item in data:
            # Apply some transformation
            processed_item = self._transform_item(item)
            processed_data.append(processed_item)

        return processed_data

    def _transform_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        # Implementation details
        return item
```

#### Key Methods

- `register_with_orchestrator()`: Register this worker with an orchestrator
- Create methods decorated with `@TaskHandler` to implement task capabilities

### Advanced Features

#### Parallel Execution

Tasks can be executed in parallel by setting the `parallel` parameter to `True`:

```python
results = await orchestrator.orchestrate_workflow(workflow, parallel=True)
```

#### Task Callbacks

You can register callbacks to be executed when a task completes:

```python
async def task_completed(result: TaskResult) -> None:
    print(f"Task {result.task_id} completed with status: {result.status}")

task_id = await orchestrator.delegate_task(
    worker_name="worker1",
    task_type="process_data",
    parameters={"data": input_data},
    callback=task_completed
)
```

#### Workflow Abort Conditions

You can configure a workflow to abort if a task fails:

```python
workflow = [
    {
        "task_type": "validate_input",
        "parameters": {"data": input_data},
        "abort_on_failure": True  # Stop if validation fails
    },
    {
        "task_type": "process_data",
        "include_previous_results": True
    }
]
```

#### Result Dependency

Tasks can access results from previous tasks:

```python
workflow = [
    {
        "task_type": "fetch_data",
        "parameters": {"source": "database"}
    },
    {
        "task_type": "transform_data",
        "include_previous_results": True  # Access previous results
    }
]
```

### Best Practices

1. **Worker Specialization**: Design workers to be specialists in specific domains or tasks
2. **Stateless Workers**: Keep workers stateless where possible to simplify scaling and fault recovery
3. **Idempotent Tasks**: Design tasks to be idempotent (can be safely repeated) to support retries
4. **Timeout Management**: Set appropriate timeouts for tasks based on their expected duration
5. **Error Handling**: Implement robust error handling in both orchestrators and workers
6. **Task Granularity**: Balance task granularity - too fine-grained increases communication overhead, too coarse-grained reduces flexibility

### Real-World Examples

The Orchestrator-Worker pattern is ideal for scenarios such as:

- **Data Processing Pipelines**: Extract, transform, load (ETL) workflows
- **Content Generation**: Multi-stage content creation with specialist agents
- **Customer Support**: Routing customer queries to specialized support agents
- **Decision Systems**: Complex decision processes requiring multiple analyses
