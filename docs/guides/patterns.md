# Agent Patterns in OpenMAS

OpenMAS provides optional modules and base classes within the `openmas.patterns` namespace to facilitate the implementation of common Multi-Agent System (MAS) design patterns. This guide highlights the patterns with built-in support and provides conceptual approaches for implementing other common workflows using core features.

## Supported Patterns with Built-in Helpers

### Orchestrator-Worker Pattern (`openmas.patterns.orchestrator`)

This pattern is useful for coordinating complex workflows where a central agent (Orchestrator) delegates tasks to specialized agents (Workers). OpenMAS provides dedicated base classes for this:

*   **`BaseOrchestratorAgent`**: Manages workflow execution (e.g., using `orchestrate_workflow`), delegates tasks (`delegate_task`), aggregates results, discovers workers (`discover_workers`), and handles potential worker failures or timeouts.
*   **`BaseWorkerAgent`**: Implements specific task logic using the `@TaskHandler` decorator. Workers typically register themselves with an orchestrator.
*   **Communication**: Uses standard OpenMAS communication (`send_request`/`send_notification`) for task delegation and result reporting.

**Benefits:**

*   Clear separation of concerns.
*   Improved scalability and maintainability.
*   Facilitates parallelism and fault tolerance in workflows.

**Example Usage:**

```python
import asyncio
from openmas.patterns.orchestrator import (
    BaseOrchestratorAgent,
    BaseWorkerAgent,
    TaskHandler
)
from openmas.config import AgentConfig
from openmas.agent import BaseAgent # Needed for main example
from openmas.logging import configure_logging, get_logger

configure_logging(log_level="INFO")
logger = get_logger(__name__)

# Define a worker agent with task handlers
class MathWorker(BaseWorkerAgent):
    # No __init__ needed unless adding custom state

    @TaskHandler(task_type="add", description="Add two numbers")
    async def add(self, a: int, b: int) -> dict:
        logger.info(f"Worker '{self.name}' adding {a} + {b}")
        return {"result": a + b}

    @TaskHandler(task_type="multiply", description="Multiply two numbers")
    async def multiply(self, a: int, b: int) -> dict:
        logger.info(f"Worker '{self.name}' multiplying {a} * {b}")
        return {"result": a * b}

# Define an orchestrator agent
class CalculationOrchestrator(BaseOrchestratorAgent):
    # No __init__ needed unless adding custom state

    async def calculate_expression(self, a: int, b: int, c: int) -> int:
        """Calculates a + (b * c) using worker agents."""
        logger.info(f"Orchestrator calculating {a} + ({b} * {c})")
        # Define a workflow sequence
        workflow = [
            {
                "task_type": "multiply", # Task handled by MathWorker
                "parameters": {"a": b, "b": c},
                "worker_name": "math_worker" # Specify the target worker
            },
            {
                "task_type": "add",      # Task handled by MathWorker
                "parameters": {"a": a},  # 'b' will come from previous result
                "include_previous_results": {"b": "result"}, # Map previous 'result' to 'b'
                "worker_name": "math_worker",
                "abort_on_failure": True
            }
        ]

        # Execute the workflow (sequentially by default)
        results = await self.orchestrate_workflow(workflow)
        logger.info(f"Workflow results: {results}")

        # Get the final result from the second step (index 1)
        final_result_dict = results.get(1, {})
        return final_result_dict.get("result", None)

# --- Main application setup ---
async def main():
    # Create agents using standard BaseAgent initialization
    # Communicators need to be compatible (e.g., HTTP)
    http_port_orch = 8000
    http_port_worker = 8001

    orch_config = AgentConfig(
        name="calc_orchestrator",
        communicator_type="http",
        service_urls={"math_worker": f"http://localhost:{http_port_worker}"},
        communicator_options={"http_port": http_port_orch}
    )
    worker_config = AgentConfig(
        name="math_worker",
        communicator_type="http",
        service_urls={"calc_orchestrator": f"http://localhost:{http_port_orch}"},
        communicator_options={"http_port": http_port_worker}
    )

    orchestrator = CalculationOrchestrator(config=orch_config)
    worker = MathWorker(config=worker_config)

    # Start agents (this runs setup and run methods)
    await orchestrator.start()
    await worker.start()

    # Worker needs to register itself with the orchestrator
    logger.info("Registering worker...")
    await worker.register_with_orchestrator(orchestrator.name)
    logger.info("Worker registered.")

    # Give a moment for registration/setup
    await asyncio.sleep(1)

    # Trigger the calculation on the orchestrator
    logger.info("Triggering calculation...")
    final_value = await orchestrator.calculate_expression(a=5, b=2, c=3)
    logger.info(f"Final Calculated Result: {final_value}") # Should be 11

    # Clean up
    logger.info("Stopping agents...")
    await worker.stop()
    await orchestrator.stop()
    logger.info("Agents stopped.")

if __name__ == "__main__":
    asyncio.run(main())
```

*(See the API documentation for `BaseOrchestratorAgent` and `BaseWorkerAgent` for more details on configuration and methods like `discover_workers`, `delegate_task`, `orchestrate_workflow` options, etc.)*

## Implementing Other Workflows using Core Features

Many other patterns rely on agents sending messages to each other in specific sequences or based on certain conditions. You can implement these using `BaseAgent` and `send_request`.

### 1. Prompt Chaining / Sequential Processing

In this pattern, the output of one agent becomes the input for the next agent in a sequence.

**Concept:** Agent A calls Agent B, Agent B processes the data and calls Agent C, and so on. The initial call might return the final result after the whole chain completes, or intermediate agents might just forward requests.

**Implementation:**

* Each agent in the chain needs the address of the *next* agent in its `service_urls` configuration.
* An agent's handler receives a request, performs its task, potentially transforms the data, and then uses `self.communicator.send_request` to call the *next* agent in the chain, passing the processed data.
* The final agent in the chain returns the result back up the call stack.

```python
# Conceptual Chaining Example
from openmas.agent import BaseAgent
import asyncio

class AgentB(BaseAgent):
    async def setup(self):
        await self.communicator.register_handler("process_b", self.handle_process)

    async def handle_process(self, data_from_a: dict) -> dict:
        # ... process data_from_a ...
        processed_data = {"b_result": data_from_a.get("a_result", "") + "_processed_by_b"}

        # Assume Agent C's logical name is 'agentC' configured in service_urls
        # self.config.service_urls["agentC"] would contain the actual address
        agent_c_service_name = "agentC"

        # Call Agent C
        final_result = await self.communicator.send_request(
            target_service=agent_c_service_name,
            method="process_c",
            params={"data_from_b": processed_data}
        )
        return final_result # Return result from C

class AgentC(BaseAgent):
     async def setup(self):
        await self.communicator.register_handler("process_c", self.handle_process)

     async def handle_process(self, data_from_b: dict) -> dict:
         # ... process data_from_b ...
         final_data = {"final": data_from_b.get("b_result", "") + "_processed_by_c"}
         return final_data

# Agent A (not shown) would initiate the call to Agent B's "process_b" handler.
# Configuration (e.g., in Agent A and B) would map logical names like "agentB"
# and "agentC" to actual addresses (e.g., http://host:port).
```

### 2. Routing / Conditional Dispatch

An agent acts as a router, deciding which subsequent agent(s) to call based on the incoming request data or its internal state.

**Concept:** Agent R receives a request, inspects the parameters or context, and forwards the request to Agent X, Agent Y, or maybe both, based on defined rules.

**Implementation:**

* The Router Agent (Agent R) needs the addresses of all potential target agents (X, Y, etc.) in its `service_urls`.
* The handler in Agent R contains the routing logic (e.g., `if/elif/else` statements based on request parameters).
* Based on the logic, Agent R uses `self.communicator.send_request` to call the appropriate target agent(s) and method(s).
* The router might aggregate responses or simply return the response from the chosen target.

```python
# Conceptual Router Example
from openmas.agent import BaseAgent
import asyncio

class RouterAgent(BaseAgent):
    async def setup(self):
        await self.communicator.register_handler("route_request", self.handle_route)

    async def handle_route(self, request_data: dict) -> dict:
        request_type = request_data.get("type")
        payload = request_data.get("payload")

        if request_type == "image":
            # Assume logical name 'imageProcessor' is configured in service_urls
            target_service = "imageProcessor"
            target_method = "process_image"
        elif request_type == "text":
            # Assume logical name 'textAnalyzer' is configured in service_urls
            target_service = "textAnalyzer"
            target_method = "analyze_text"
        else:
            return {"error": "Unknown request type"}

        # Forward the request to the chosen service
        result = await self.communicator.send_request(
            target_service=target_service,
            method=target_method,
            params=payload # Pass the original payload
        )
        return result

# Other agents (imageProcessor, textAnalyzer) would define the respective
# handlers (process_image, analyze_text).
# The RouterAgent's config would map these logical names to addresses.
```

### 3. Parallel Execution / Fan-Out

An agent sends the same (or similar) request to multiple other agents simultaneously and potentially aggregates the results.

**Concept:** Agent P receives a task, splits it or identifies multiple relevant workers (W1, W2, W3), sends requests to all workers in parallel, waits for all responses, and combines them.

**Implementation:**

* The Parallelizer Agent (Agent P) needs the addresses of all potential worker agents (W1, W2, W3) in its `service_urls`.
* Agent P creates multiple `send_request` calls as `asyncio` tasks.
* It uses `asyncio.gather(*tasks)` to run these requests concurrently and wait for all of them to complete.
* It then processes the list of results returned by `asyncio.gather`.

```python
# Conceptual Parallelizer Example
from openmas.agent import BaseAgent
import asyncio

class ParallelAgent(BaseAgent):
    async def setup(self):
        await self.communicator.register_handler("process_in_parallel", self.handle_parallel)

    async def handle_parallel(self, task_data: dict) -> dict:
        # Assume worker_services list comes from config or discovery
        # self.config.service_urls should contain mappings for "worker1", "worker2", etc.
        worker_services = ["worker1", "worker2", "worker3"] # Logical names
        tasks = []

        for worker_name in worker_services:
            task = self.communicator.send_request(
                target_service=worker_name,
                method="perform_subtask", # Assume workers implement this
                params={"data": task_data} # Send same data to all
            )
            tasks.append(task)

        # Execute all requests concurrently
        # return_exceptions=True allows processing partial success
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        aggregated_results = []
        errors = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                errors.append(f"Worker {worker_services[i]} failed: {res}")
            elif isinstance(res, dict) and res.get("error"): # Handle application errors
                 errors.append(f"Worker {worker_services[i]} error: {res['error']}")
            else:
                aggregated_results.append(res)

        return {
            "aggregated": aggregated_results,
            "errors": errors
        }

# Worker agents (worker1, worker2, etc.) would define the 'perform_subtask' handler.
# The ParallelAgent's config would map these logical names to addresses.
```

### Other Patterns

While OpenMAS provides specific helpers for the Orchestrator-Worker pattern, many other MAS patterns can be implemented using the core `BaseAgent` and appropriate communicators:

*   **Publish/Subscribe:** Can be effectively implemented using the `MqttCommunicator` with an MQTT broker, or by building a custom registry/dispatcher agent using standard communicators.
*   **Contract Net Protocol:** Involves agents broadcasting task announcements, receiving bids, and awarding contracts. This can be built using `send_request` and `send_notification` with custom logic within agents to manage the bidding and awarding process.
*   **Service Discovery:** A dedicated registry agent can be created where other agents register their services (`register_handler`) and query for available services (`send_request`). The `BaseOrchestratorAgent`'s `discover_workers` method provides a basic form of discovery for the Orchestrator-Worker pattern.

Building these patterns involves designing the interaction protocols and implementing the corresponding logic within your `BaseAgent` subclasses.

## Future Enhancements

While these patterns are implementable today using core features, dedicated framework helpers or classes for patterns like Chaining or Routing might be added in future OpenMAS versions to further simplify their implementation.
