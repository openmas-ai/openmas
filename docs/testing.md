# Testing Multi-Agent Systems with OpenMAS

This document provides comprehensive guidance on testing multi-agent systems built with OpenMAS, focusing on robust testing practices using the provided test utilities.

## Testing Philosophy

OpenMAS follows a Test-Driven Development (TDD) approach:

1. Write failing tests first
2. Implement the minimum code required to make the tests pass
3. Refactor the code while keeping the tests passing

## Unit vs. Integration Tests

OpenMAS distinguishes between two types of tests:

### Unit Tests

Unit tests verify isolated components with all external dependencies mocked:

- Located in `tests/unit/`
- Require complete isolation using mocks for all external dependencies
- Must never be skipped due to unavailability of external dependencies
- Examples: testing agent logic, communicator functionality, configuration parsing

### Integration Tests

Integration tests verify how components work together:

- Located in `tests/integration/`
- May use mocks where appropriate
- May use actual dependencies if available
- Should be skipped if required dependencies are unavailable
- Examples: testing communication between actual agents, testing with real MCP, MQTT, or gRPC servers

## Testing Utilities

OpenMAS provides two primary testing utilities:

1. **MockCommunicator**: A mock implementation of the BaseCommunicator for testing agents without real network dependencies.
2. **AgentTestHarness**: A comprehensive test harness for creating, managing, and testing agent instances with MockCommunicator integration.

## Using the MockCommunicator

The `MockCommunicator` allows you to precisely control and verify agent communications during tests.

### Basic Setup

```python
import pytest
from openmas.testing import MockCommunicator

@pytest.fixture
def mock_communicator():
    """Create a mock communicator for testing."""
    comm = MockCommunicator(agent_name="test-agent")
    yield comm
    # Verify all expectations were met
    comm.verify()
```

### Setting Expectations and Verifying Requests

```python
@pytest.mark.asyncio
async def test_agent_requests(mock_communicator):
    # Set up expectations
    mock_communicator.expect_request(
        target_service="data-service",
        method="get_user",
        params={"user_id": "123"},
        response={"name": "Test User", "email": "test@example.com"}
    )

    # Make the request
    result = await mock_communicator.send_request(
        target_service="data-service",
        method="get_user",
        params={"user_id": "123"}
    )

    # Assert the response
    assert result["name"] == "Test User"
    assert result["email"] == "test@example.com"

    # Verify all expectations were met
    mock_communicator.verify_all_expectations_met()
```

### Advanced Parameter Matching

The enhanced MockCommunicator supports various parameter matching strategies:

```python
import re
from openmas.testing import MockCommunicator

@pytest.mark.asyncio
async def test_advanced_parameter_matching():
    comm = MockCommunicator(agent_name="test-agent")

    # 1. Match any parameters
    comm.expect_request(
        target_service="service",
        method="any_params",
        params=None,  # Match any parameters
        response={"status": "ok"}
    )

    # 2. Regex pattern matching for string values
    comm.expect_request(
        target_service="service",
        method="pattern_match",
        params={"query": re.compile(r"^user_\d+$")},
        response={"matches": True}
    )

    # 3. Custom matcher function
    def validate_positive(value):
        return isinstance(value, int) and value > 0

    comm.expect_request(
        target_service="service",
        method="custom_match",
        params={"value": validate_positive},
        response={"valid": True}
    )

    # 4. Nested dictionary matching
    comm.expect_request(
        target_service="service",
        method="nested_match",
        params={
            "user": {
                "profile": {"age": 30}
            }
        },
        response={"matched": True}
    )

    # Execute the requests and verify
    await comm.send_request("service", "any_params", {"can": "be anything"})
    await comm.send_request("service", "pattern_match", {"query": "user_123"})
    await comm.send_request("service", "custom_match", {"value": 42})
    await comm.send_request("service", "nested_match", {
        "user": {
            "profile": {"age": 30, "name": "John"}  # Extra fields are fine
        }
    })

    comm.verify()
```

### Testing Notifications

```python
@pytest.mark.asyncio
async def test_notifications(mock_communicator):
    # Set up expected notification
    mock_communicator.expect_notification(
        target_service="logging-service",
        method="log_event",
        params={"level": "info", "message": "Test event"}
    )

    # Send the notification
    await mock_communicator.send_notification(
        target_service="logging-service",
        method="log_event",
        params={"level": "info", "message": "Test event"}
    )

    # Verify the expectation was met
    mock_communicator.verify()
```

### Testing Handler Registration and Triggering

```python
@pytest.mark.asyncio
async def test_handler_registration(mock_communicator):
    # Define a test handler
    async def test_handler(message):
        content = message["content"]
        return {"processed": content["value"] * 2}

    # Register the handler
    await mock_communicator.register_handler("process", test_handler)

    # Trigger the handler with test parameters
    result = await mock_communicator.trigger_handler(
        method="process",
        params={"value": 42}
    )

    # Assert the handler processed the message correctly
    assert result == {"processed": 84}
```

### Testing Error Conditions

```python
from openmas.exceptions import ServiceNotFoundError

@pytest.mark.asyncio
async def test_error_conditions(mock_communicator):
    # Set up an exception to be raised
    exception = ServiceNotFoundError("service-x not found")
    mock_communicator.expect_request_exception(
        target_service="service-x",
        method="get_data",
        params={"id": "123"},
        exception=exception
    )

    # Expect the exception to be raised
    with pytest.raises(ServiceNotFoundError) as excinfo:
        await mock_communicator.send_request(
            target_service="service-x",
            method="get_data",
            params={"id": "123"}
        )

    # Assert the exception message
    assert str(excinfo.value) == "service-x not found"
    mock_communicator.verify()
```

## Using the AgentTestHarness

The `AgentTestHarness` simplifies testing agent behavior by providing a structured way to create, start, stop, and interact with agent instances during tests. It's especially powerful for multi-agent testing scenarios.

Key features:
- Creates agent instances with properly configured MockCommunicators
- Manages the agent lifecycle (start/stop) through convenient context managers
- Provides utilities for simulating and verifying agent communications
- Supports multi-agent testing with per-agent MockCommunicator instances
- Enables testing of complex interactions between multiple agents

### Basic Agent Testing

```python
import pytest
from openmas.agent import Agent
from openmas.testing import AgentTestHarness

class TestAgentClass(Agent):
    async def setup(self):
        await super().setup()
        await self.communicator.register_handler("process", self.handle_process)

    async def handle_process(self, message):
        data = message.get("data", 0)
        # Call an external service
        result = await self.communicator.send_request(
            "math-service", "calculate", {"operation": "double", "value": data}
        )
        return {"result": result["value"]}

@pytest.fixture
def agent_harness():
    return AgentTestHarness(
        TestAgentClass,
        default_config={"name": "test-agent", "service_urls": {}}
    )

@pytest.mark.asyncio
async def test_agent_processing(agent_harness):
    # Create an agent with the harness
    agent = await agent_harness.create_agent()

    # Set up expectations for the external service call
    agent.communicator.expect_request(
        "math-service", "calculate",
        {"operation": "double", "value": 5},
        {"value": 10}
    )

    # Start the agent using a context manager
    async with agent_harness.running_agent(agent):
        # Trigger the handler to test
        result = await agent_harness.trigger_handler(
            agent, "process", {"data": 5}
        )

        # Verify the result
        assert result == {"result": 10}

        # Verify all expected communications occurred
        agent_harness.verify_all_communicators()
```

### Multi-Agent Testing

The AgentTestHarness provides robust support for testing interactions between multiple agents, with each agent having its own unique MockCommunicator:

```python
@pytest.mark.asyncio
async def test_multi_agent_interaction(agent_harness):
    # Create multiple agents, each getting a unique MockCommunicator
    agent1 = await agent_harness.create_agent(name="agent1")
    agent2 = await agent_harness.create_agent(name="agent2")
    agent3 = await agent_harness.create_agent(name="agent3")

    # Link the agents for direct communication
    # This sets up service_urls in both agent configs and communicators,
    # and links the mock communicators for direct message passing
    await agent_harness.link_agents(agent1, agent2)
    await agent_harness.link_agents(agent1, agent3)

    # Start the agents to register their handlers
    async with agent_harness.running_agents(agent1, agent2, agent3):
        # Store test data in agents (will be needed for testing inter-agent communication)
        await agent_harness.trigger_handler(agent1, "store_data", {"key": "test", "value": "from-agent1"})
        await agent_harness.trigger_handler(agent2, "store_data", {"key": "test", "value": "from-agent2"})
        await agent_harness.trigger_handler(agent3, "store_data", {"key": "test", "value": "from-agent3"})

        # Method 1: Using the harness's send_request helper for cleaner testing
        # This method directly routes the request to the target agent's handler
        result1 = await agent_harness.send_request(agent1, "agent2", "get_data", {"key": "test"})
        assert result1["value"] == "from-agent2"

        # Method 2: Using the agent's communicator directly
        # In this case, you may need to set up expectations on the receiving agent
        agent3.communicator.expect_request(
            "agent3", "get_data", {"key": "test"}, {"key": "test", "value": "from-agent3"}
        )
        result2 = await agent1.communicator.send_request("agent3", "get_data", {"key": "test"})
        assert result2["value"] == "from-agent3"

        # Test sending a notification between agents
        agent2.communicator.expect_notification("agent2", "callback", {"event": "update"})
        await agent1.communicator.send_notification("agent2", "callback", {"event": "update"})

        # Verify all expectations were met across all communicators
        agent_harness.verify_all_communicators()
```

The harness tracks all agent communicators in the `communicators` dictionary, allowing for targeted setup and verification:

```python
# You can directly access a specific agent's communicator
agent1_comm = agent_harness.communicators["agent1"]
agent2_comm = agent_harness.communicators["agent2"]

# Set up specific expectations for each communicator
agent1_comm.expect_request("external-service", "get_data", {"id": "123"}, {"result": "data1"})
agent2_comm.expect_notification("monitoring", "log", {"level": "info"})

# Verify expectations for all agents at once
agent_harness.verify_all_communicators()

# Or verify a specific agent's expectations
agent1_comm.verify()
```

### Linking Agents for Testing

When testing interactions between multiple agents, it's crucial to properly link them using the `link_agents` method:

```python
await agent_harness.link_agents(agent1, agent2, agent3)
```

This method does several important things:
1. Updates each agent's `config.service_urls` to include references to the other agents
2. Adds entries in each agent's `communicator.service_urls` dictionary
3. Links the mock communicators to enable direct message routing between agents

Always link agents before attempting to test communication between them. Without proper linking:
- Agents won't know how to route messages to each other
- The MockCommunicator won't know how to route requests to the appropriate handler
- You'll get errors about missing service URLs or unexpected requests

### Using the Harness's send_request Method

The AgentTestHarness provides a convenient `send_request` method to simplify testing communication between agents:

```python
@pytest.mark.asyncio
async def test_inter_agent_communication(agent_harness):
    # Create and link two agents
    agent1 = await agent_harness.create_agent(name="sender")
    agent2 = await agent_harness.create_agent(name="receiver")

    await agent_harness.link_agents(agent1, agent2)

    # Start both agents to register handlers
    async with agent_harness.running_agents(agent1, agent2):
        # Store test data in the receiver agent
        await agent_harness.trigger_handler(
            agent2, "store_data", {"key": "test_key", "value": "test_value"}
        )

        # Use send_request to route a request from sender to receiver
        # This automatically handles the routing and expectations
        response = await agent_harness.send_request(
            agent1, "receiver", "get_data", {"key": "test_key"}
        )

        # Verify the response
        assert response["key"] == "test_key"
        assert response["value"] == "test_value"
```

The `send_request` method offers several advantages:
- Simplifies inter-agent testing by handling the request/response flow
- Automatically routes the request to the target agent's handler
- No need to manually set up expectations for basic testing
- Works with the established links between agents

## Test Organization and Structure

OpenMAS tests are organized following this structure:

```
tests/
  unit/
    agent/        # Tests for agent classes
    cli/          # Tests for CLI components
    communication/ # Tests for communicators
    deployment/   # Tests for deployment utilities
    patterns/     # Tests for pattern implementations
  integration/
    core/         # Integration tests for core functionality
    grpc/         # Integration tests for gRPC communication
    mcp/          # Integration tests for MCP communication
    mqtt/         # Integration tests for MQTT communication
```

### File and Class Naming Conventions

- Test files should be named `test_*.py`
- Test classes should be named `Test*`
- Test methods should be named `test_*`

### Using pytest Marks for Test Categories

OpenMAS uses pytest marks to categorize tests:

```python
import pytest

@pytest.mark.unit
def test_basic_function():
    # Unit test implementation
    pass

@pytest.mark.integration
def test_integration_case():
    # Integration test implementation
    pass

@pytest.mark.mcp
def test_mcp_integration():
    # Test that requires MCP dependencies
    pass

@pytest.mark.grpc
def test_grpc_feature():
    # Test that requires gRPC dependencies
    pass

@pytest.mark.mqtt
def test_mqtt_feature():
    # Test that requires MQTT dependencies
    pass
```

These marks can be used to select specific test categories when running tests:

```bash
# Run only unit tests
pytest -m unit

# Run integration tests that use MCP
pytest -m "integration and mcp"

# Run all tests except integration tests
pytest -m "not integration"
```

## Running Tests

Use tox to run the test suite:

```bash
# Run all tests
tox

# Run specific test environment
tox -e py310-mcp

# Run with specific Python version
tox -e py310

# Run linting checks
tox -e lint
```

Available test environments:

- `py310`: Basic tests with Python 3.10
- `py310-grpc`: Tests that require gRPC
- `py310-mcp`: Tests that require MCP
- `py310-mqtt`: Tests that require MQTT
- `lint`: Code quality checks
- `coverage`: Test coverage reporting

## Testing Best Practices

### Writing Good Tests

1. **Test in isolation**: Each test should be independent and not rely on the state from previous tests
2. **Mock external dependencies**: Use `MockCommunicator` to avoid real network calls in unit tests
3. **Be explicit about test categories**: Use appropriate pytest marks to indicate test requirements
4. **Use descriptive names**: Test names should clearly describe what is being tested
5. **Assert expected outcomes**: Make specific assertions about the expected behavior

### Testing Patterns and Best Practices

Follow this structure for agent tests:

1. **Arrange**: Create and configure the agent and its expectations
2. **Act**: Trigger the behavior to test
3. **Assert**: Verify the results and expectations

```python
@pytest.mark.asyncio
async def test_agent_behavior(agent_harness):
    # ARRANGE
    agent = await agent_harness.create_agent()
    agent.communicator.expect_request(
        "service", "method", {"param": "value"}, {"result": "success"}
    )

    # ACT
    async with agent_harness.running_agent(agent):
        result = await agent_harness.trigger_handler(
            agent, "process", {"data": "input"}
        )

    # ASSERT
    assert result == expected_value
    agent_harness.verify_all_communicators()
```

### Testing Error Handling

Always test how your agents handle errors:

```python
@pytest.mark.asyncio
async def test_agent_error_handling(agent_harness):
    agent = await agent_harness.create_agent()

    # Set up a service to return an error
    agent.communicator.expect_request_exception(
        "service", "method", {"param": "value"},
        Exception("Service error")
    )

    # Test that the agent handles the error gracefully
    async with agent_harness.running_agent(agent):
        result = await agent_harness.trigger_handler(
            agent, "process_with_error_handling", {"data": "input"}
        )

        # Agent should return a proper error response rather than crashing
        assert result["status"] == "error"
        assert "Service error" in result["message"]
```

## Special Cases

### Testing with Optional Dependencies

When testing features that depend on optional dependencies, use the appropriate pytest marks:

```python
@pytest.mark.mcp
def test_mcp_feature():
    # This test will be skipped if MCP dependencies are not installed
    from openmas.communication.mcp import McpSseCommunicator
    # Test implementation...
```

### Testing Async Code

Use `pytest-asyncio` for testing asynchronous code:

```python
@pytest.mark.asyncio
async def test_async_function():
    # Test async functionality
    result = await some_async_function()
    assert result == expected_value
```

### Testing Timeouts

Test how your agent behaves when services are slow:

```python
@pytest.mark.asyncio
async def test_agent_timeout_handling(agent_harness):
    agent = await agent_harness.create_agent()

    # In a real test, you would mock the timeout behavior
    # For demonstration, we'll just set up an expectation
    agent.communicator.expect_request_exception(
        "slow-service", "get_data", {"id": "123"},
        TimeoutError("Request timed out")
    )

    async with agent_harness.running_agent(agent):
        result = await agent_harness.trigger_handler(
            agent, "process_with_timeout", {"id": "123"}
        )

        assert result["status"] == "timeout"
        assert result["fallback_data"] is not None
```
