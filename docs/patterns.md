# Agent Patterns & Workflows in OpenMAS

OpenMAS provides the flexibility to implement various common Multi-Agent System (MAS) design patterns and workflows. While the framework offers specific helper classes for the Orchestrator-Worker pattern, many others can be built using the core `BaseAgent`, communication (`send_request`/`send_notification`), and configuration features.

This guide outlines the built-in support and provides conceptual approaches for implementing other common workflows.

## Supported Patterns with Built-in Helpers

### Orchestrator-Worker Pattern (`openmas.patterns.orchestrator`)

This pattern is useful for coordinating complex workflows where a central agent (Orchestrator) delegates tasks to specialized agents (Workers). OpenMAS provides dedicated base classes for this:

* **`BaseOrchestratorAgent`**: Manages workflow execution (e.g., using `orchestrate_workflow`), delegates tasks (`delegate_task`), aggregates results, discovers workers (`discover_workers`), and handles potential worker failures or timeouts.
* **`BaseWorkerAgent`**: Implements specific task logic using the `@TaskHandler` decorator. Workers typically register themselves with an orchestrator.
* **Communication**: Uses standard OpenMAS communication (`send_request`/`send_notification`) for task delegation and result reporting.

**Benefits:** Clear separation of concerns, improved scalability and maintainability, facilitates parallelism and fault tolerance.

**Example Usage:**

    # Indented Code Block (Conceptual Example)
    from openmas.patterns.orchestrator import BaseOrchestratorAgent, BaseWorkerAgent, TaskHandler
    from openmas.config import AgentConfig
    from openmas.agent import BaseAgent # Needed for main example
    import asyncio

    # --- Worker ---
    class ImageAnalysisWorker(BaseWorkerAgent):
        @TaskHandler(task_type="detect_objects")
        async def detect(self, image_url: str) -> dict:
            # ... logic to download and analyze image ...
            results = {"objects": ["cat", "sofa"]}
            return results

    # --- Orchestrator ---
    class ImageProcessingOrchestrator(BaseOrchestratorAgent):
        async def process_image_set(self, urls: list[str]) -> list:
            # Example: Parallel execution (if orchestrate_workflow supports it,
            # otherwise implement custom parallel delegation)
            tasks = []
            for url in urls:
                # Assume 'image_worker' is the registered name
                tasks.append(
                    self.delegate_task(
                        worker_name="image_worker",
                        task_type="detect_objects",
                        parameters={"image_url": url}
                    )
                )
            all_results = await asyncio.gather(*tasks)
            return all_results

    # --- Main Setup (Conceptual) ---
    # async def main():
    #     # Create orchestrator and worker instances with compatible communicators
    #     # Start agents
    #     # Worker registers with orchestrator
    #     # Trigger orchestrator's process_image_set method
    #     # Stop agents

*(See the API documentation for `BaseOrchestratorAgent` and `BaseWorkerAgent` for more details.)*

## Implementing Other Workflows using Core Features

Many other patterns rely on agents sending messages to each other in specific sequences or based on certain conditions. You can implement these using `BaseAgent` and `send_request`.

### 1. Prompt Chaining / Sequential Processing

In this pattern, the output of one agent becomes the input for the next agent in a sequence.

**Concept:** Agent A calls Agent B, Agent B processes the data and calls Agent C, and so on. The initial call might return the final result after the whole chain completes, or intermediate agents might just forward requests.

**Implementation:**

* Each agent in the chain needs the address of the *next* agent in its `service_urls` configuration.
* An agent's handler receives a request, performs its task, potentially transforms the data, and then uses `self.communicator.send_request` to call the *next* agent in the chain, passing the processed data.
* The final agent in the chain returns the result back up the call stack.

    # Indented Code Block (Conceptual Chaining)
    class AgentB(BaseAgent):
        async def setup(self):
            await self.communicator.register_handler("process_b", self.handle_process)

        async def handle_process(self, data_from_a: dict) -> dict:
            # ... process data_from_a ...
            processed_data = {"b_result": data_from_a.get("a_result", "") + "_processed_by_b"}

            # Get address of Agent C from config
            # agent_c_service_name = "agentC" # Logical name

            # Call Agent C
            final_result = await self.communicator.send_request(
                target_service="agentC", # Logical name from config
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

    # Agent A would initiate the call to Agent B's "process_b" handler.

### 2. Routing / Conditional Dispatch

An agent acts as a router, deciding which subsequent agent(s) to call based on the incoming request data or its internal state.

**Concept:** Agent R receives a request, inspects the parameters or context, and forwards the request to Agent X, Agent Y, or maybe both, based on defined rules.

**Implementation:**

* The Router Agent (Agent R) needs the addresses of all potential target agents (X, Y, etc.) in its `service_urls`.
* The handler in Agent R contains the routing logic (e.g., `if/elif/else` statements based on request parameters).
* Based on the logic, Agent R uses `self.communicator.send_request` to call the appropriate target agent(s) and method(s).
* The router might aggregate responses or simply return the response from the chosen target.

    # Indented Code Block (Conceptual Router)
    class RouterAgent(BaseAgent):
        async def setup(self):
            await self.communicator.register_handler("route_request", self.handle_route)

        async def handle_route(self, request_data: dict) -> dict:
            request_type = request_data.get("type")
            payload = request_data.get("payload")

            if request_type == "image":
                target_service = "imageProcessor"
                target_method = "process_image"
            elif request_type == "text":
                target_service = "textAnalyzer"
                target_method = "analyze_text"
            else:
                return {"error": "Unknown request type"}

            # Forward the request to the chosen service
            result = await self.communicator.send_request(
                target_service=target_service, # Logical name from config
                method=target_method,
                params=payload # Pass the original payload
            )
            return result

### 3. Parallel Execution / Fan-Out

An agent sends the same (or similar) request to multiple other agents simultaneously and potentially aggregates the results.

**Concept:** Agent P receives a task, splits it or identifies multiple relevant workers (W1, W2, W3), sends requests to all workers in parallel, waits for all responses, and combines them.

**Implementation:**

* The Parallelizer Agent (Agent P) needs the addresses of all potential worker agents (W1, W2, W3) in its `service_urls`.
* Agent P creates multiple `send_request` calls as `asyncio` tasks.
* It uses `asyncio.gather(*tasks)` to run these requests concurrently and wait for all of them to complete.
* It then processes the list of results returned by `asyncio.gather`.

    # Indented Code Block (Conceptual Parallelizer)
    import asyncio

    class ParallelAgent(BaseAgent):
        async def setup(self):
            await self.communicator.register_handler("process_in_parallel", self.handle_parallel)

        async def handle_parallel(self, task_data: dict) -> dict:
            # Assume worker_list comes from config or discovery
            worker_services = ["worker1", "worker2", "worker3"] # Logical names
            tasks = []

            for worker_name in worker_services:
                task = self.communicator.send_request(
                    target_service=worker_name,
                    method="perform_subtask",
                    params={"data": task_data} # Send same data to all
                )
                tasks.append(task)

            # Execute all requests concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True) # Handle potential errors

            # Aggregate results
            aggregated_results = []
            errors = []
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    errors.append(f"Worker {worker_services[i]} failed: {res}")
                else:
                    aggregated_results.append(res)

            return {
                "aggregated": aggregated_results,
                "errors": errors
            }

## Future Enhancements

While these patterns are implementable today using core features, dedicated framework helpers or classes for patterns like Chaining or Routing might be added in future OpenMAS versions to further simplify their implementation.
