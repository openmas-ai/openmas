# Example Prompts for Contributors

This document provides sample prompts to help contributors create consistent and high-quality examples for OpenMAS.

## General Notes on Creating Examples

When creating examples for OpenMAS, follow these key principles:

1. **Test-Driven Development**: Begin by writing the test for the example before implementing it
2. **Completeness**: Ensure examples include all required files: agents, configuration, READMEs, and tests
3. **Minimum Working Examples**: Make examples focused and minimal while still demonstrating the feature
4. **Clear Documentation**: Include clear explanations in README.md and code comments
5. **Consistency**: Follow the established patterns in existing examples

## Sample Prompt: Multi-Agent HTTP Example

Here's a detailed prompt for creating a multi-agent HTTP example:

```
Prompt: Multi-Agent "Hello World" with HTTP Communicator

Objective: Create, configure, and test a simple two-agent system using HTTP communication. The primary goal is to demonstrate how agents can communicate using the HTTP communicator.

Context: This example will feature a sender agent that sends messages to a receiver agent using HTTP communication. Both agents need to implement the required BaseAgent methods (setup, run, shutdown). The example will demonstrate basic request-response patterns over HTTP.

Task:
1. **Navigate:** Ensure you are in the `openmas/` project root directory.

2. **Create Directory Structure:**
   ```bash
   mkdir -p examples/01_communication_basics/00_http_client_server/agents/{sender,receiver}
   ```

3. **Implement Agents:**
   * Create `examples/01_communication_basics/00_http_client_server/agents/sender/agent.py`:
     * Define `SenderAgent(BaseAgent)` class implementing all required methods
     * In `async def run(self):`, send an HTTP request to the receiver using `self.communicator.send_request()`
     * Include appropriate logging and error handling

   * Create `examples/01_communication_basics/00_http_client_server/agents/receiver/agent.py`:
     * Define `ReceiverAgent(BaseAgent)` class implementing all required methods
     * Register a handler in `setup()` method to process incoming requests
     * Include appropriate logging and responses

4. **Create Package Initialization Files:**
   * Create `__init__.py` files in all appropriate directories to ensure proper importing

5. **Create Project Configuration:**
   * Create `examples/01_communication_basics/00_http_client_server/openmas_project.yml`:
     * Define both agents with their appropriate modules/classes
     * Configure the HTTP communicator with appropriate ports
     * Add service URLs to enable agents to find each other

6. **Create Requirements File:**
   * Create a minimal `requirements.txt` file if any additional dependencies are needed

7. **Implement Tests:**
   * Create `examples/01_communication_basics/00_http_client_server/test_example.py`:
     * Import `AgentTestHarness` and agent classes
     * Use expectation-based testing pattern to validate communication
     * Set up appropriate request expectations
     * Verify agent behavior and communication

8. **Create Documentation:**
   * Write a detailed `README.md` explaining:
     * Purpose of the example
     * Core concepts demonstrated (HTTP communication)
     * How to run the example
     * Expected results
     * Project structure

9. **Update tox.ini:**
   * Add a new environment for running the example's tests
   * Ensure proper environment setup and dependencies

10. **Test Thoroughly:**
    * Run the test via tox to verify it works
    * Fix any issues that arise
    * Test manually to ensure proper functionality

**Key Implementation Details:**

1. **SenderAgent:**
   ```python
   async def run(self) -> None:
       """Run the agent, sending a request to the receiver."""
       self.logger.info("Sender sending HTTP request")
       try:
           response = await self.communicator.send_request(
               target_service="receiver",
               method="process_message",
               params={"message": "Hello from HTTP sender!"}
           )
           self.logger.info(f"Received response: {response}")
       except Exception as e:
           self.logger.error(f"Error sending request: {e}")
   ```

2. **ReceiverAgent:**
   ```python
   async def setup(self) -> None:
       """Set up the receiver agent."""
       self.logger.info("Setting up ReceiverAgent")
       # Register handler for incoming requests
       await self.communicator.register_handler(
           "process_message", self.handle_message
       )

   async def handle_message(self, payload: dict) -> dict:
       """Handle incoming messages."""
       self.logger.info(f"Received message: {payload}")
       return {"status": "success", "response": "Message received!"}
   ```

3. **Project Configuration:**
   ```yaml
   name: examples/01_communication_basics/00_http_client_server
   version: 0.1.0
   agents:
     sender: "agents/sender"
     receiver: "agents/receiver"
   default_config:
     log_level: INFO
   communicator_defaults:
     type: http
     options:
       http_port: 8000
   agent_configs:
     receiver:
       communicator_options:
         http_port: 8001
     sender:
       service_urls:
         receiver: "http://localhost:8001"
   ```

4. **Test Strategy:**
   - Use `AgentTestHarness` to create and manage agent instances
   - Set up expectations for HTTP requests/responses
   - Verify that agents implement the expected communication pattern
   ```python
   # Example test snippet
   sender_harness = AgentTestHarness(SenderAgent)
   sender = await sender_harness.create_agent(name="sender")

   # Set up expected HTTP request
   sender.communicator.expect_request(
       target_service="receiver",
       method="process_message",
       params={"message": "Hello from HTTP sender!"},
       response={"status": "success", "response": "Message received!"}
   )

   # Run the test
   async with sender_harness.running_agent(sender):
       await sender.run()
       sender.communicator.verify()
   ```
```

## Sample Prompt: BDI Agent Example

```
Prompt: BDI Agent Pattern Example

Objective: Create a simple example demonstrating the Belief-Desire-Intention (BDI) agent pattern using OpenMAS's BdiAgent class. This example should showcase how to create and manage beliefs, desires, and intentions within an agent.

Context: The BDI architecture is a popular agent design pattern where agents maintain beliefs about the world, desires (goals) they want to achieve, and intentions (current plans). This example will demonstrate how to implement a simple BDI agent in OpenMAS.

Task:
1. **Navigate:** Ensure you are in the `openmas/` project root directory.

2. **Create Directory Structure:**
   ```bash
   mkdir -p examples/03_agent_patterns/00_bdi_agent/agents/gardener
   ```

3. **Implement Agents:**
   * Create `examples/03_agent_patterns/00_bdi_agent/agents/gardener/agent.py`:
     * Define `GardenerAgent(BdiAgent)` that maintains beliefs about a garden
     * Implement intentions to water plants, remove weeds, etc. based on beliefs
     * Use the BDI pattern to make decisions based on the agent's current state

4. **Create Package Initialization Files:**
   * Create `__init__.py` files in all appropriate directories

5. **Create Project Configuration:**
   * Create `examples/03_agent_patterns/00_bdi_agent/openmas_project.yml`:
     * Define the gardener agent and its configuration
     * Use a mock communicator for testing

6. **Implement Tests:**
   * Create `examples/03_agent_patterns/00_bdi_agent/test_example.py`:
     * Test the agent's ability to update beliefs
     * Test decision-making based on beliefs
     * Verify that intentions are executed appropriately

7. **Create Documentation:**
   * Write a detailed `README.md` explaining the BDI pattern and how it's implemented

8. **Update tox.ini:**
   * Add a new environment for testing the BDI example
```

## Adding New Examples to the Documentation

When adding new examples, ensure you:

1. Update the main examples documentation in `docs/examples.md`
2. Add the new tox environment to the project's `tox.ini` file
3. Ensure the example follows existing patterns and directory structures
4. Include complete documentation in the example's README.md

## Testing Your Examples

All examples must be thoroughly tested using the following approach:

1. **Write Tests First**: Create a `test_example.py` file that validates the example's functionality
2. **Use AgentTestHarness**: For agent-based examples, use `AgentTestHarness` to test agent behavior
3. **Expectation-Based Testing**: For communication tests, set up expectations and verify them
4. **Add to tox.ini**: Create a dedicated tox environment for your example
5. **Run Both Automated and Manual Tests**: Ensure the example works both via automated tests and when run manually

For more detailed information on testing approaches, refer to:
- [Testing Utilities Guide](../guides/testing-utilities.md)
- [Testing Strategy for Contributors](testing_strategy.md)

## Testing Your Examples: Advanced Testing Patterns

OpenMAS provides two main testing approaches, each with specific use cases:

### 1. Streamlined Helper Functions (Recommended for Most Cases)

This approach uses helper functions that simplify common testing patterns:

```python
import pytest
from agents.receiver import ReceiverAgent
from agents.sender import SenderAgent
from openmas.testing import expect_sender_request, multi_running_agents, setup_sender_receiver_test

@pytest.mark.asyncio
async def test_hello_pair_mock():
    # Set up sender and receiver agents in one line
    sender_harness, receiver_harness, sender, receiver = await setup_sender_receiver_test(
        SenderAgent, ReceiverAgent
    )

    # Set up expectations with the simplified helper
    expect_sender_request(
        sender,
        "receiver",
        "process_message",
        {"message": "Hello from sender!"},
        {"status": "success", "response": "Message received!"}
    )

    # Run both agents with a single context manager
    async with multi_running_agents(sender_harness, sender, receiver_harness, receiver):
        await sender.run()
        sender.communicator.verify()
```

**When to use this approach:**
- For sender-receiver test patterns (the most common scenario)
- When you want minimal boilerplate code
- For examples that demonstrate typical agent interactions
- When clarity and brevity are important

### 2. Direct Harness and Expectations (For Greater Control)

This approach gives you more direct control over harness creation and expectation setup:

```python
import pytest
from openmas.testing import AgentTestHarness
from agents.my_agent import MySpecialAgent

@pytest.mark.asyncio
async def test_custom_agent_behavior():
    # Create and configure a harness with custom options
    harness = AgentTestHarness(MySpecialAgent,
                              default_config={"custom_option": True})

    # Create an agent with specific configuration
    agent = await harness.create_agent(name="custom-agent",
                                     config={"special_mode": "advanced"})

    # Set up complex expectations directly
    agent.communicator.expect_request(
        target_service="external-service",
        method="complex_operation",
        params={"nested": {"data": {"structure": 123}}},
        response={"result": {"detailed": "response"}}
    )

    # Run the agent and test its behavior
    async with harness.running_agent(agent):
        await agent.perform_special_operation()
        agent.communicator.verify()

        # Assert custom state changes
        assert agent.operation_count == 1
        assert agent.last_result["detailed"] == "response"
```

**When to use this approach:**
- For testing agents with complex configuration requirements
- When you need to assert agent state changes beyond just communications
- For non-standard testing scenarios (beyond simple sender-receiver)
- When testing specialized agent patterns (e.g., BDI agents, orchestrators)
