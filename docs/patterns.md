# Common Patterns in OpenMAS

This document describes common patterns and best practices for building multi-agent systems with OpenMAS.

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

# Patterns in OpenMAS

OpenMAS provides helper classes and utilities for implementing common patterns in multi-agent systems.

## Orchestrator-Worker Pattern

The Orchestrator-Worker pattern is a powerful design pattern for coordinating complex workflows within a multi-agent system. It consists of:

1. **Orchestrator Agent**: A central coordinator that manages workflow execution by delegating tasks to specialized workers and aggregating their results.
2. **Worker Agents**: Specialized agents that perform specific tasks within their domain of expertise.
3. **Task Communication**: A standardized protocol for task delegation, status reporting, and result retrieval.

### Key Components

OpenMAS implements the Orchestrator-Worker pattern with the following components:

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

Below is a simple example of how to use the Orchestrator-Worker pattern in OpenMAS:

```python
from openmas.patterns.orchestrator import (
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
2. Implement task handlers using the `@TaskHandler` decorator
3. Optionally override `setup()` to add additional initialization logic

```python
from openmas.patterns.orchestrator import BaseWorkerAgent, TaskHandler

class DataProcessingWorker(BaseWorkerAgent):
    async def setup(self) -> None:
        # Call parent setup to register standard handlers
        await super().setup()

        # Additional setup logic if needed
        self.logger.info("DataProcessingWorker initialized")

    @TaskHandler(task_type="clean_data", description="Clean and validate input data")
    async def clean_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove invalid entries and normalize data."""
        cleaned_data = []
        for item in data:
            if self._is_valid(item):
                cleaned_data.append(self._normalize(item))
        return cleaned_data

    @TaskHandler(task_type="transform_data", description="Transform data structure")
    async def transform_data(self, data: List[Dict[str, Any]], format: str = "flat") -> List[Dict[str, Any]]:
        """Transform data into the requested format."""
        if format == "flat":
            return self._flatten_data(data)
        elif format == "nested":
            return self._nest_data(data)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _is_valid(self, item: Dict[str, Any]) -> bool:
        # Custom validation logic
        return "id" in item and "value" in item

    def _normalize(self, item: Dict[str, Any]) -> Dict[str, Any]:
        # Custom normalization logic
        return {k: v.strip() if isinstance(v, str) else v for k, v in item.items()}

    def _flatten_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Implementation of data flattening
        return data

    def _nest_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Implementation of data nesting
        return data

# Register with orchestrator
async def start_worker():
    worker = DataProcessingWorker(name="data_processor")
    await worker.start()
    # Register with orchestrator (could be done in setup() too)
    success = await worker.register_with_orchestrator("data_pipeline_orchestrator")
    if success:
        worker.logger.info("Successfully registered with orchestrator")

#### Key Worker Methods

- `register_with_orchestrator()`: Register the worker with an orchestrator
- `_send_task_result()`: Send task results back to the orchestrator
- `_handle_execute_task()`: Process incoming task requests

### Advanced Usage: Dynamic Worker Discovery

In larger systems, you may want to dynamically discover workers:

```python
from openmas.patterns.orchestrator import BaseOrchestratorAgent

class DynamicOrchestrator(BaseOrchestratorAgent):
    async def setup(self) -> None:
        await super().setup()
        # Set a shorter default timeout
        self.default_timeout = 30.0

    async def run(self) -> None:
        """Main orchestrator loop."""
        while True:
            # Discover workers periodically
            await self.discover_workers()
            self.logger.info(f"Known workers: {list(self._workers.keys())}")

            # Process any pending tasks or workflows
            # ...

            await asyncio.sleep(60)  # Rediscover every minute

    async def process_with_capability(self, task_type: str, data: Any) -> Optional[Any]:
        """Find a worker with the required capability and delegate a task."""
        worker_name = self.find_worker_for_task(task_type)
        if not worker_name:
            self.logger.warning(f"No worker found with capability: {task_type}")
            return None

        task_id = await self.delegate_task(
            worker_name=worker_name,
            task_type=task_type,
            parameters={"data": data}
        )

        # Wait for the result
        result = await self.get_task_result(task_id)
        if result and result.status == "success":
            return result.result
        else:
            self.logger.error(f"Task failed: {result.error if result else 'Task timed out'}")
            return None
```

### Using the TaskHandler Decorator

The `@TaskHandler` decorator makes it easy to register methods as task handlers:

```python
from openmas.patterns.orchestrator import BaseWorkerAgent, TaskHandler

class AnalyticsWorker(BaseWorkerAgent):
    @TaskHandler(task_type="summarize", description="Generate summary statistics")
    async def summarize_data(self,
                           data: List[Dict[str, Any]],
                           fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Generate summary statistics for the provided data."""
        if not data:
            return {"count": 0}

        fields_to_summarize = fields or list(data[0].keys())
        result = {"count": len(data)}

        for field in fields_to_summarize:
            if field in data[0] and isinstance(data[0][field], (int, float)):
                values = [item[field] for item in data if field in item]
                result[f"{field}_avg"] = sum(values) / len(values) if values else 0
                result[f"{field}_min"] = min(values) if values else 0
                result[f"{field}_max"] = max(values) if values else 0

        return result
```

### Workflow Orchestration with Error Handling

```python
from openmas.patterns.orchestrator import BaseOrchestratorAgent

class RobustOrchestrator(BaseOrchestratorAgent):
    async def process_data_pipeline(self,
                                  input_data: List[Dict[str, Any]],
                                  retry_count: int = 3) -> Dict[str, Any]:
        """Process a data pipeline with error handling and retries."""
        # Define workflow steps
        workflow = [
            {
                "task_type": "validate_input",
                "parameters": {"data": input_data},
                "abort_on_failure": True  # Stop workflow if validation fails
            },
            {
                "task_type": "clean_data",
                "include_previous_results": True
            },
            {
                "task_type": "transform_data",
                "parameters": {"format": "normalized"},
                "include_previous_results": True
            },
            {
                "task_type": "generate_report",
                "include_previous_results": True
            }
        ]

        # Execute workflow with retry logic
        attempt = 0
        while attempt < retry_count:
            try:
                results = await self.orchestrate_workflow(workflow)
                # If we get here, workflow completed successfully
                return results[3].get("result", {})  # Return result of final step
            except Exception as e:
                attempt += 1
                self.logger.warning(
                    f"Workflow attempt {attempt} failed: {str(e)}. "
                    f"{'Retrying...' if attempt < retry_count else 'Giving up.'}"
                )
                if attempt < retry_count:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        # If we get here, all attempts failed
        return {"status": "failed", "error": "Maximum retry attempts exceeded"}
```

### Parallel Task Execution

The orchestrator can execute tasks in parallel for improved performance:

```python
async def analyze_multiple_datasets(self, datasets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analyze multiple datasets in parallel."""
    # Find workers with analytics capability
    analytics_workers = []
    for name, info in self._workers.items():
        if "analyze_data" in info.capabilities:
            analytics_workers.append(name)

    if not analytics_workers:
        raise ValueError("No workers with 'analyze_data' capability found")

    # Distribute tasks among workers
    tasks = []
    for i, dataset in enumerate(datasets):
        # Distribute tasks round-robin among available workers
        worker_name = analytics_workers[i % len(analytics_workers)]

        task_id = await self.delegate_task(
            worker_name=worker_name,
            task_type="analyze_data",
            parameters={"dataset": dataset}
        )
        tasks.append(task_id)

    # Collect results in parallel
    results = []
    for task_id in tasks:
        result = await self.get_task_result(task_id)
        if result and result.status == "success":
            results.append(result.result)

    return results
```

## Integration with Model Context Protocol (MCP)

For agents using MCP for capabilities like LLM integration, you can combine the Orchestrator-Worker pattern with MCP:

```python
from mcp.client.session import ClientSession
from mcp.types import TextContent

from openmas.patterns.orchestrator import BaseWorkerAgent, TaskHandler

class LLMWorker(BaseWorkerAgent):
    async def setup(self) -> None:
        await super().setup()
        # Initialize MCP client
        self.mcp_client = ClientSession(api_key="YOUR_API_KEY")

    @TaskHandler(task_type="text_summarization", description="Summarize text with LLM")
    async def summarize_text(self, text: str, max_length: int = 200) -> str:
        """Summarize text using LLM through MCP."""
        async with self.mcp_client as session:
            messages = [
                TextContent(
                    role="user",
                    text=f"Summarize the following text in {max_length} characters or less:\n\n{text}"
                )
            ]

            response = await session.generate_response(messages)
            return response.content[0].text

    @TaskHandler(task_type="sentiment_analysis", description="Analyze sentiment of text")
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text using LLM through MCP."""
        async with self.mcp_client as session:
            messages = [
                TextContent(
                    role="user",
                    text=f"Analyze the sentiment of the following text. Respond with a JSON object containing 'sentiment' (positive, negative, or neutral) and 'confidence' (0-1):\n\n{text}"
                )
            ]

            response = await session.generate_response(messages)
            # Parse JSON from response
            import json
            try:
                return json.loads(response.content[0].text)
            except json.JSONDecodeError:
                return {"sentiment": "unknown", "confidence": 0}
```

## Chaining Pattern

The Chaining pattern provides a way to execute a sequence of service calls, where each step can depend on the results of previous steps. This pattern is useful for implementing multi-stage processes where operations need to be performed in order.

### Key Components

OpenMAS implements the Chaining pattern with the following components:

- `ServiceChain`: A class for defining and executing a chain of service calls
- `ChainBuilder`: A builder for creating chains with a fluent interface
- `ChainStep`: A model representing a step in the chain
- `ChainStepResult`: A model representing the result of executing a step
- `ChainResult`: A model representing the result of executing the entire chain

### Benefits

- **Sequential Execution**: Execute operations in a specific order
- **Data Flow**: Pass data between steps in the chain
- **Error Handling**: Handle errors at each step and abort or continue as needed
- **Retries**: Configure retry policies for individual steps
- **Conditional Execution**: Skip steps based on conditions
- **Transformations**: Transform inputs and outputs at each step

### Example Usage

```python
from openmas.patterns.chaining import ChainBuilder

# Create a chain builder
chain = ChainBuilder(communicator, name="weather_forecast_chain")

# Add steps to the chain
chain.add_step(
    target_service="auth_service",
    method="authenticate",
    parameters={"api_key": "my_api_key"},
    name="auth",
    retry_count=2,
)

chain.add_step(
    target_service="location_service",
    method="get_coordinates",
    parameters={"city": "New York"},
    name="location",
    transform_output=lambda resp: resp.get("coordinates"),
)

# Execute the chain
result = await chain.execute()

if result.successful:
    print(f"Final result: {result.final_result}")
else:
    print(f"Chain execution failed: {result.results[-1].error}")
```

## Routing Pattern

The Routing pattern provides a flexible way to dispatch requests to different handlers based on various criteria. This pattern is useful for implementing request handling systems that need to route requests based on content, type, or other properties.

### Key Components

OpenMAS implements the Routing pattern with the following components:

- `Router`: A class for defining routing rules and dispatching requests
- `RoutingAgent`: A base agent class that includes routing capabilities
- `Route`: A class representing a routing rule
- Decorators: Various decorators for defining routing rules on methods

### Benefits

- **Flexible Routing**: Route requests based on method name, parameters, content, or custom conditions
- **Priority-Based**: Specify priorities for routing rules to control which rules take precedence
- **Transparent Forwarding**: Forward requests to other services without additional code
- **Centralized Routing Logic**: Keep all routing logic in one place for easier maintenance
- **Declarative Syntax**: Use decorators for a clean, declarative syntax

### Example Usage

```python
from openmas.patterns.routing import (
    RoutingAgent,
    route_method,
    route_param,
    route_content,
    route_default
)

class ExampleRoutingAgent(RoutingAgent):
    @route_method(method="get_user")
    async def handle_get_user(self, user_id: str, **kwargs):
        # Handle get_user method
        return {"user_id": user_id, "name": f"User {user_id}"}

    @route_param(param_name="action", param_value="create")
    async def handle_create_action(self, **kwargs):
        # Handle create actions
        return {"status": "created"}

    @route_default()
    async def handle_default(self, **kwargs):
        # Handle any request that doesn't match other routes
        return {"status": "unknown_request"}
```

## Combining Patterns

These patterns are designed to work together, allowing you to build complex agent systems:

### Orchestrator-Worker with Routing

```python
class RoutingOrchestrator(BaseOrchestratorAgent, RoutingAgent):
    async def setup(self) -> None:
        await BaseOrchestratorAgent.setup(self)
        await RoutingAgent.setup(self)

    @route_method(method="process")
    async def handle_process(self, data: Dict[str, Any], **kwargs):
        # Use orchestration for processing
        workflow = [
            {"task_type": "validate", "parameters": {"data": data}},
            {"task_type": "transform", "include_previous_results": True}
        ]
        return await self.orchestrate_workflow(workflow)
```

### Chaining with Routing

```python
class ApiGateway(RoutingAgent):
    @route_method(method="get_user_weather")
    async def handle_get_user_weather(self, user_id: str, **kwargs):
        chain = ChainBuilder(self.communicator, "user_weather_chain")

        chain.add_step(
            target_service="user_service",
            method="get_user",
            parameters={"user_id": user_id}
        )

        chain.add_step(
            target_service="location_service",
            method="get_user_location",
            parameters={"user_id": user_id}
        )

        chain.add_step(
            target_service="weather_service",
            method="get_forecast",
            transform_input=lambda ctx: {
                "coordinates": ctx["get_user_location"]
            }
        )

        result = await chain.execute()
        return {
            "user": result.results[0].result,
            "location": result.results[1].result,
            "weather": result.results[2].result
        }
```
