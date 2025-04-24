# Testing Multi-Agent Systems with SimpleMas

This document provides comprehensive guidance on testing multi-agent systems built with SimpleMas, focusing on robust testing practices using the provided test utilities.

## Testing Utilities

SimpleMAS provides two primary testing utilities:

1. **MockCommunicator**: A mock implementation of the BaseCommunicator for testing agents without real network dependencies.
2. **AgentTestHarness**: A comprehensive test harness for creating, managing, and testing agent instances with MockCommunicator integration.

## Using the MockCommunicator

The `MockCommunicator` allows you to precisely control and verify agent communications during tests.

### Basic Setup

```python
import pytest
from simple_mas.testing import MockCommunicator

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
from simple_mas.testing import MockCommunicator

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
from simple_mas.exceptions import ServiceNotFoundError

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

### Examining Call History

```python
@pytest.mark.asyncio
async def test_call_history(mock_communicator):
    # Set up expected request
    mock_communicator.expect_request(
        "service1", "method1", {"param": "value"}, {"result": "success"}
    )

    # Make the request
    await mock_communicator.send_request(
        "service1", "method1", {"param": "value"}
    )

    # Check the call history
    assert len(mock_communicator.calls) == 1
    assert mock_communicator.calls[0].method_name == "send_request"
    assert mock_communicator.calls[0].args[0] == "service1"  # target_service
    assert mock_communicator.calls[0].args[1] == "method1"   # method
    assert mock_communicator.calls[0].args[2] == {"param": "value"}  # params
```

## Using the AgentTestHarness

The `AgentTestHarness` simplifies testing agent behavior by providing a structured way to create, start, stop, and interact with agent instances during tests.

### Basic Agent Testing

```python
import pytest
from simple_mas.agent import Agent
from simple_mas.testing import AgentTestHarness

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
    agent_harness.communicator.expect_request(
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
        agent_harness.communicator.verify()
```

### Multi-Agent Testing

The enhanced AgentTestHarness includes utilities for testing interactions between multiple agents:

```python
@pytest.mark.asyncio
async def test_multi_agent_interaction(agent_harness):
    # Create two agents
    agent1 = await agent_harness.create_agent(name="agent1")
    agent2 = await agent_harness.create_agent(name="agent2")

    # Set up handler on agent2
    async def handle_query(message):
        return {"data": f"Processed {message['content'].get('query', '')}"}

    await agent2.communicator.register_handler("query", handle_query)

    # Link the agents for direct communication
    await agent_harness.link_agents(agent1, agent2)

    # Start both agents using the running_agents context manager
    async with agent_harness.running_agents(agent1, agent2):
        # Set up the expected request from agent1 to agent2
        agent_harness.communicators["agent1"].expect_request(
            "agent2", "query", {"query": "test_data"}, None
        )

        # Agent1 sends a request to agent2
        response = await agent1.communicator.send_request(
            "agent2", "query", {"query": "test_data"}
        )

        # Verify the response
        assert response == {"data": "Processed test_data"}

        # Verify all expectations were met across all communicators
        agent_harness.verify_all_communicators()
```

### Testing Asynchronous Operations

The harness provides a utility for waiting for asynchronous conditions:

```python
@pytest.mark.asyncio
async def test_async_operations(agent_harness):
    agent = await agent_harness.create_agent()

    # Add a flag to track async operations
    agent.operation_complete = False

    async def delayed_operation():
        await asyncio.sleep(0.1)
        agent.operation_complete = True

    async with agent_harness.running_agent(agent):
        # Start the async operation
        asyncio.create_task(delayed_operation())

        # Wait for the operation to complete
        result = await agent_harness.wait_for(
            lambda: agent.operation_complete,
            timeout=0.5,
            check_interval=0.01
        )

        # Verify the operation completed
        assert result is True
        assert agent.operation_complete is True
```

## Testing Patterns and Best Practices

### Test Structure

Follow this structure for agent tests:

1. **Arrange**: Create and configure the agent and its expectations
2. **Act**: Trigger the behavior to test
3. **Assert**: Verify the results and expectations

```python
@pytest.mark.asyncio
async def test_agent_behavior(agent_harness):
    # ARRANGE
    agent = await agent_harness.create_agent()
    agent_harness.communicator.expect_request(
        "service", "method", {"param": "value"}, {"result": "success"}
    )

    # ACT
    async with agent_harness.running_agent(agent):
        result = await agent_harness.trigger_handler(
            agent, "process", {"data": "input"}
        )

    # ASSERT
    assert result == expected_value
    agent_harness.communicator.verify()
```

### Testing Error Handling

Always test how your agents handle errors:

```python
@pytest.mark.asyncio
async def test_agent_error_handling(agent_harness):
    agent = await agent_harness.create_agent()

    # Set up a service to return an error
    agent_harness.communicator.expect_request_exception(
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

### Testing Timeouts

Test how your agent behaves when services are slow:

```python
@pytest.mark.asyncio
async def test_agent_timeout_handling(agent_harness):
    agent = await agent_harness.create_agent()

    # In a real test, you would mock the timeout behavior
    # For demonstration, we'll just set up an expectation
    agent_harness.communicator.expect_request_exception(
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

## Integration Testing

For testing complete agent systems with real communication:

```python
@pytest.mark.asyncio
async def test_full_agent_system():
    # Create harnesses for different agent types
    agent1_harness = AgentTestHarness(AgentType1)
    agent2_harness = AgentTestHarness(AgentType2)
    agent3_harness = AgentTestHarness(AgentType3)

    # Create the agents
    agent1 = await agent1_harness.create_agent(name="agent1")
    agent2 = await agent2_harness.create_agent(name="agent2")
    agent3 = await agent3_harness.create_agent(name="agent3")

    # Set up real in-memory connections between agents
    await agent1_harness.link_agents(agent1, agent2, agent3)

    # Start all agents
    async with agent1_harness.running_agent(agent1):
        async with agent2_harness.running_agent(agent2):
            async with agent3_harness.running_agent(agent3):
                # Trigger the system behavior
                result = await agent1_harness.trigger_handler(
                    agent1, "start_workflow", {"data": "test"}
                )

                # Wait for the workflow to complete
                success = await agent1_harness.wait_for(
                    lambda: getattr(agent1, "workflow_complete", False),
                    timeout=2.0
                )

                assert success
                assert result["status"] == "success"
```

## Performance Testing

For performance testing, measure response times and throughput:

```python
import time
import statistics
import pytest

@pytest.mark.asyncio
async def test_agent_performance(agent_harness):
    agent = await agent_harness.create_agent()

    # Configure expected responses
    for i in range(100):
        agent_harness.communicator.expect_request(
            "data-service", "get_item", {"id": str(i)},
            {"item": f"Item {i}", "value": i}
        )

    # Measure response times
    response_times = []

    async with agent_harness.running_agent(agent):
        for i in range(100):
            start_time = time.time()
            await agent_harness.trigger_handler(
                agent, "process_item", {"id": str(i)}
            )
            end_time = time.time()
            response_times.append(end_time - start_time)

    # Analyze performance
    avg_time = statistics.mean(response_times)
    p95_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile

    # Assert performance meets requirements
    assert avg_time < 0.01  # Average response time under 10ms
    assert p95_time < 0.02  # 95% of responses under 20ms
```
