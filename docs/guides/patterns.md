# Agent Patterns in OpenMAS

OpenMAS provides optional modules and base classes within the `openmas.patterns` namespace to facilitate the implementation of common Multi-Agent System (MAS) design patterns. This guide highlights the patterns with built-in support.

## Supported Patterns

### Orchestrator-Worker Pattern (`openmas.patterns.orchestrator`)

This pattern is useful for coordinating complex workflows where a central agent (Orchestrator) delegates tasks to specialized agents (Workers).

*   **Orchestrator Agent (`BaseOrchestratorAgent`)**: Manages workflow execution, delegates tasks, aggregates results, and handles potential worker failures or timeouts.
*   **Worker Agents (`BaseWorkerAgent`)**: Implement specific task logic using the `@TaskHandler` decorator.
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

## Other Patterns (Implementation using Core Features)

While OpenMAS provides specific helpers for the patterns above, many other MAS patterns can be implemented using the core `BaseAgent` and appropriate communicators:

*   **Publish/Subscribe:** Can be effectively implemented using the `MqttCommunicator` with an MQTT broker, or by building a custom registry/dispatcher agent using standard communicators.
*   **Contract Net Protocol:** Involves agents broadcasting task announcements, receiving bids, and awarding contracts. This can be built using `send_request` and `send_notification` with custom logic within agents to manage the bidding and awarding process.
*   **Service Discovery:** A dedicated registry agent can be created where other agents register their services (`register_handler`) and query for available services (`send_request`).

Building these patterns involves designing the interaction protocols and implementing the corresponding logic within your `BaseAgent` subclasses.
