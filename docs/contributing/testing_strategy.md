# OpenMAS Testing Strategy (for Contributors)

This document outlines the testing strategy for the `openmas` framework itself, providing guidance for contributors on test types, locations, and execution.

*For information on how to test applications built **with** OpenMAS, please see the user guide: [Testing Your Agents](../guides/testing-utilities.md).*

## Goals

The OpenMAS internal testing framework addresses several key goals:

- Ensure correctness of individual framework components (agents, communicators, config, etc.).
- Prevent regressions when implementing new features or refactoring.
- Validate framework behavior in isolation and integration scenarios.
- Properly test optional features and communicators (like MCP, gRPC, MQTT).
- Provide end-to-end validation via example applications.

## Testing Philosophy

OpenMAS follows a Test-Driven Development (TDD) approach internally:

1. Write failing tests first.
2. Implement the minimum code required to make the tests pass.
3. Refactor the code while keeping the tests passing.

This ensures that features are well-tested and code quality remains high.

## Tooling

OpenMAS uses standard Python testing tools:

- `pytest`: Primary test runner.
- `pytest-asyncio`: Testing async code.
- `pytest-mock`: Mocking dependencies.
- `tox`: Test automation and environment management via directory targeting.

## Test Levels & Locations

Tests are organized primarily by directory structure within the `tests/` directory, reflecting the type of test and its dependencies.

### Unit Tests (`tests/unit/`)

Unit tests verify isolated components with all external dependencies mocked.

- **Location:** `tests/unit/`
- **Purpose:** Test individual classes and functions (e.g., `BaseAgent` methods, config loading logic) with complete isolation.
- **Dependencies:** External dependencies (Communicators, I/O, network calls, file system access) are **always** mocked using `pytest-mock` or framework utilities like `MockCommunicator`.
- **Execution:** Run via the `tox -e unit` environment.
- **Requirement:** Must never be skipped due to the unavailability of external dependencies. They should be fast and self-contained.

### Integration Tests (`tests/integration/`)

Integration tests verify how framework components work together or interact with external protocols/libraries. They are subdivided based on dependency requirements.

- **Location:** `tests/integration/`
- **Purpose:** Test interactions between components (e.g., `BaseAgent` with `HttpCommunicator`) or with external services/protocols (e.g., connecting to a real MQTT broker).
- **Dependencies:** May use mocks (`MockCommunicator`, `AgentTestHarness`) or actual dependencies (like specific communicator libraries or running services).
- **Execution:** Run via various `tox -e integration-*` environments.
- **Requirement:** Tests relying on *actual external services* (like a running MQTT broker or specific MCP server setup) **must** be skipped (using `pytest.mark.skipif`) if the required service/dependency is unavailable in the test environment. Any test that is executed (not skipped) must pass.

#### Core Integration Tests (`tests/integration/core/`)

- **Location:** `tests/integration/core/`
- **Purpose:** Test core feature interactions without optional extras (e.g., agent lifecycle with `HttpCommunicator`).
- **Execution:** Included in the `tox -e integration-mock` environment.
- **Dependencies:** Primarily test interactions between core components, typically using mocks like `MockCommunicator` or `AgentTestHarness` for simulating communication.

#### Mocked Integration Tests (`tests/integration/<feature>/mock/`)

- **Example Location:** `tests/integration/mcp/mock/`
- **Purpose:** Test integration with optional features (like MCP, gRPC) using mocks instead of real services. Allows testing the integration logic (e.g., how `McpAgent` uses `McpSseCommunicator`) without needing the actual service running.
- **Execution:** Included in the `tox -e integration-mock` environment.
- **Dependencies:** Requires the feature's libraries installed (e.g., `mcp` via `openmas[mcp]`) but mocks the actual service interaction (e.g., using `AgentTestHarness` which injects `MockCommunicator`).

#### Real Service Integration Tests (`tests/integration/<feature>/real/` or `tests/integration/<feature>/`)

- **Example Locations:** `tests/integration/mcp/real/`, `tests/integration/grpc/`, `tests/integration/mqtt/`
- **Purpose:** Test integration with optional features (like MCP, gRPC, MQTT) against *real* services or libraries. These verify the actual communication protocol implementation works correctly.
- **Execution:** Run via dedicated `tox` environments (e.g., `tox -e integration-real-mcp`, `tox -e integration-real-grpc`, `tox -e integration-real-mqtt`).
- **Dependencies:** Require the feature's libraries *and* potentially a running instance of the service (e.g., an MQTT broker, a specific test MCP server). These tests **must** use `pytest.mark.skipif` to check for service availability and skip gracefully if absent.

### Example Tests (`examples/*/`)

Example tests run the actual example applications end-to-end, primarily for framework validation.

- **Location:** `examples/*/` (Test logic often in `test_example.py` within each example).
- **Purpose:** Framework dogfooding and end-to-end feature validation in a realistic context.
- **Execution:** Run via dedicated `tox` environments (e.g., `tox -e example-00a-hello-single`).
- **Note:** These validate that the framework enables the creation of working applications for specific scenarios.

## Using the Testing Harness and Mock Communicator

OpenMAS provides powerful testing utilities that are used across all test levels:

### MockCommunicator Overview

`MockCommunicator` is used to mock agent communication in isolation. Key aspects:

1. **Expectation Based Testing:** It uses an expectations pattern - you define what calls are expected and with what parameters, then verify they were made.

2. **Available Methods:**
   - `expect_request()`: Set up an expected outgoing request with a predefined response
   - `expect_notification()`: Set up an expected outgoing notification
   - `trigger_handler()`: Directly trigger an agent's registered handler for testing
   - `verify()`: Check that all expected requests/notifications were made

3. **Common Pattern:**
   ```python
   # Set expectation for outgoing calls
   communicator.expect_request(
       target_service="service",
       method="operation",
       params={"expected": "params"},
       response={"mock": "response"}
   )

   # Run agent code that should make that call
   await agent.do_something()

   # Verify expectations
   communicator.verify()
   ```

### AgentTestHarness Overview

`AgentTestHarness` manages agent lifecycle with mocked communicators. Key aspects:

1. **Agent Class Requirements:** You must pass in an agent class (not instance) that implements all abstract methods from `BaseAgent` (`setup`, `run`, `shutdown`).

2. **Agent Creation Pattern:**
   ```python
   # Create harness with your agent class
   harness = AgentTestHarness(MyAgent)

   # Create an agent instance
   agent = await harness.create_agent(name="test-agent")

   # The harness provides a MockCommunicator
   agent.communicator.expect_request(...)

   # Context manager to start/stop the agent
   async with harness.running_agent(agent):
       # Agent is now running
       # Test interactions here
   ```

3. **Multi-Agent Testing:** For multiple agents, create separate harnesses for each agent type:
   ```python
   sender_harness = AgentTestHarness(SenderAgent)
   receiver_harness = AgentTestHarness(ReceiverAgent)

   sender = await sender_harness.create_agent(name="sender")
   receiver = await receiver_harness.create_agent(name="receiver")

   # Set up expectations for what sender will send
   sender.communicator.expect_request(...)

   # Run both agents in context managers
   async with sender_harness.running_agent(sender), receiver_harness.running_agent(receiver):
       # Test interactions
   ```

### Common Testing Patterns

1. **Testing an agent's outgoing messages:**
   ```python
   # Set up expectation
   agent.communicator.expect_request(
       target_service="service", method="operation",
       params={"key": "value"}, response={"result": "success"}
   )

   # Run the agent logic that should make this call
   await agent.do_work()

   # Verify all expected calls were made
   agent.communicator.verify()
   ```

2. **Testing an agent's handler logic:**
   ```python
   # Register handlers (usually happens in agent.setup())
   await agent.setup()

   # Trigger the handler directly
   response = await agent.communicator.trigger_handler(
       method="handle_request",
       params={"data": "test"}
   )

   # Verify the response
   assert response == {"status": "success", "result": "processed"}
   ```

3. **Testing agent state after operations:**
   ```python
   # Run some agent logic
   await agent.process_data(test_input)

   # Verify state changes
   assert agent.data_processed == True
   assert len(agent.results) == 1
   ```

For detailed examples and advanced usage, refer to the unit/integration tests in the codebase.

### Helper Functions for Common Testing Patterns

For common testing scenarios, OpenMAS provides high-level helper functions that significantly reduce boilerplate code:

1. **`setup_sender_receiver_test()`**: Creates and configures a sender-receiver test scenario in a single call.

   ```python
   # Instead of manually creating two harnesses and agents:
   sender_harness, receiver_harness, sender, receiver = await setup_sender_receiver_test(
       SenderAgent, ReceiverAgent
   )
   ```

2. **`expect_sender_request()`**: Sets up request expectations with a cleaner interface:

   ```python
   # Instead of directly using communicator.expect_request:
   expect_sender_request(
       sender,
       "receiver",
       "handle_message",
       {"greeting": "hello"},
       {"status": "received", "message": "Hello received!"}
   )
   ```

3. **`expect_notification()`**: Sets up notification expectations with a cleaner interface:

   ```python
   expect_notification(
       sender,
       "logging-service",
       "log_event",
       {"level": "info", "message": "Test completed"}
   )
   ```

4. **`multi_running_agents()`**: Manages multiple agent lifecycles in a single context manager:

   ```python
   # Instead of nested context managers:
   async with multi_running_agents(sender_harness, sender, receiver_harness, receiver):
       # Both agents are now running
       await sender.run()
   ```

**When to Use Helpers vs. Direct Approach:**

- **Use helpers** for standard test scenarios and when readability is a priority
- **Use direct harness/communicator** for tests that need custom configuration, complex state assertions, or non-standard patterns

For examples demonstrating OpenMAS functionality (like those in `examples/`), the helper functions are generally preferred for clarity and conciseness.

## Running Tests via `tox`

`tox` is the **required** way to run tests for contribution, ensuring isolated environments and correct dependencies based on targeted directories. Use `poetry run tox ...` to ensure tox uses the project's Poetry environment.

### Local Development (Fast Feedback):

These environments are fast and don't require external services.

- `poetry run tox`: Runs the default set: `lint`, `unit`, `integration-mock`.
- `poetry run tox -e lint`: Run linters, formatters (check mode), and type checker.
- `poetry run tox -e unit`: Run only unit tests (very fast).
- `poetry run tox -e integration-mock`: Run core and mocked integration tests.
- `poetry run tox -e coverage`: Run unit and mock integration tests and generate a coverage report.

### Local Development (Specific Real Services):

Run these if you have the corresponding service (e.g., MQTT broker, specific MCP server) running locally and configured.

- `poetry run tox -e integration-real-mcp`: Run MCP integration tests against real services/libs.
- `poetry run tox -e integration-real-grpc`: Run gRPC integration tests against real services/libs.
- `poetry run tox -e integration-real-mqtt`: Run MQTT integration tests against a real MQTT broker.

### CI Pull Request Checks (Fast):

CI should run the fast checks on every pull request:

- `poetry run tox -e lint`
- `poetry run tox -e unit`
- `poetry run tox -e integration-mock`

### Full CI Runs (e.g., on Merge/Release):

Full CI runs should execute all environments, including those requiring real services. The CI environment must be configured to provide these services (e.g., start Docker containers).

- `poetry run tox` (which includes `lint`, `unit`, `integration-mock`)
- `poetry run tox -e integration-real-mcp`
- `poetry run tox -e integration-real-grpc`
- `poetry run tox -e integration-real-mqtt`
- `poetry run tox -e coverage`
- All `example-*` environments.

**Important:** Running `pytest` directly is **discouraged** for final checks as it bypasses the environment setup and dependency management handled by `tox`, potentially leading to incorrect results or missed/incorrectly skipped tests.

## Handling Optional Dependencies

OpenMAS handles optional dependencies primarily through:

1.  **Directory Structure:** Separating tests requiring optional dependencies into specific directories (e.g., `integration/mcp/`, `integration/grpc/`).
2.  **Tox Environments with Extras:** Dedicated `tox` environments (e.g., `integration-mock`, `integration-real-mcp`) install the necessary extras (defined in `pyproject.toml` using `poetry install --extras ...`) and target the relevant test directories.
3.  **Pytest `skipif`:** Tests requiring real services (in `integration/.../real/`) **must** use `pytest.mark.skipif` to check for the availability of the service or necessary libraries/configuration, ensuring they are skipped gracefully if the dependencies aren't met.

## Mocking Strategy

- **Unit tests (`tests/unit/`):** All external dependencies MUST be mocked (`pytest-mock`).
- **Core integration tests (`tests/integration/core/`):** Typically use mocks for external systems (`MockCommunicator`, `AgentTestHarness`).
- **Mocked integration tests (`tests/integration/.../mock/`):** Use the feature's library but mock the actual network/service interaction (e.g., using `MockCommunicator` or specific mocking utilities like `McpTestHarness` configured for mocking).
- **Real service integration tests (`tests/integration/.../real/`):** Use the real libraries and attempt to connect to real services (or test harnesses simulating them).
- **Example tests (`examples/*/`):** Run actual example code, potentially against real services depending on the example.

## Common Testing Challenges

Here are some common issues you might encounter when writing tests:

### 1. "Cannot instantiate abstract class X with abstract methods..."

This means your agent class doesn't implement all required abstract methods from BaseAgent. At minimum, implement:
- `async def setup(self) -> None`
- `async def run(self) -> None`
- `async def shutdown(self) -> None`

### 2. "AttributeError: 'MockCommunicator' object has no attribute 'send'"

The method is named `send_request()`, not `send()`. Use:

```python
await communicator.send_request(
    target_service="service_name",
    method="method_name",
    params={"key": "value"}
)
```

### 3. "Unexpected request: X:Y with params: Z. Available requests: none"

You need to set up expectations for all requests:

```python
communicator.expect_request(
    target_service="X",
    method="Y",
    params={"key": "value"},
    response={"result": "success"}
)
```

## Contribution Guide

When contributing tests to OpenMAS:

1.  Add unit tests to `tests/unit/` matching the module structure in `src/`. Ensure all external dependencies are mocked.
2.  Add integration tests for core features (no optional extras) to `tests/integration/core/`. Use mocks where appropriate.
3.  Add integration tests for features requiring optional extras:
    * If the test *mocks* the external service interaction, place it in `tests/integration/<feature>/mock/` (e.g., `tests/integration/mcp/mock/`). Ensure it runs in the `integration-mock` tox environment.
    * If the test requires a *real* service/library interaction, place it in `tests/integration/<feature>/real/` (e.g., `tests/integration/mcp/real/`) or `tests/integration/<feature>/` if no mock/real split exists for that feature. Use `skipif` appropriately for real service tests. Ensure it runs in the correct `integration-real-<feature>` tox environment.
4.  Ensure tests run correctly within their designated `tox` environment(s).
5.  Do **not** rely on `pytest` markers (`@pytest.mark.<feature>`) for controlling test execution; rely on the directory structure and `tox` environments.
