# Testing Multi-Agent Systems with SimpleMas

This document provides guidance on testing multi-agent systems built with SimpleMas.

## Testing Strategies

### Unit Testing Agents

Test individual agent handlers:

```python
import pytest
from simple_mas import Agent
from simple_mas.communication.mcp import MCPCommunicator

@pytest.fixture
async def test_agent():
    agent = Agent(
        name="test_agent",
        communicator=MCPCommunicator(
            agent_name="test_agent",
            service_urls={}
        )
    )

    @agent.handler("echo")
    async def handle_echo(params):
        return {"echo": params.get("message", "")}

    await agent.start()
    yield agent
    await agent.stop()

async def test_echo_handler(test_agent):
    # Test the echo handler directly
    handler = test_agent._handlers["echo"]
    result = await handler({"message": "hello"})
    assert result == {"echo": "hello"}
```

## Using the MockCommunicator

SimpleMAS provides a mock communicator specifically designed for testing. The `MockCommunicator` allows you to:

1. Set up expected requests and predefined responses
2. Record calls made to it for later assertions
3. Simulate handler registration and triggering
4. Verify that all expected interactions occurred

### Basic Usage

```python
import pytest
from simple_mas import Agent
from simple_mas.testing import MockCommunicator

@pytest.fixture
async def agent_with_mock():
    # Create a mock communicator
    mock_comm = MockCommunicator(agent_name="test_agent")

    # Create an agent using the mock communicator
    agent = Agent(
        name="test_agent",
        communicator=mock_comm
    )

    # Set up a request handler
    @agent.handler("test_handler")
    async def handle_test(params):
        return {"result": params.get("value", "") + "_processed"}

    await agent.start()
    yield agent, mock_comm
    await agent.stop()

async def test_agent_with_mock(agent_with_mock):
    agent, mock_comm = agent_with_mock

    # Set up an expected request and response
    mock_comm.expect_request(
        target_service="external_service",
        method="get_data",
        params={"id": "123"},
        response={"data": "test_data"}
    )

    # Have the agent make a request
    response = await agent.send_request(
        target_service="external_service",
        method="get_data",
        params={"id": "123"}
    )

    # Verify the response
    assert response == {"data": "test_data"}

    # Verify all expectations were met
    mock_comm.verify_all_expectations_met()
```

### Advanced Features

#### Setting Up Expected Requests with Specific Responses

```python
# Set up a response for a specific request
mock_comm.expect_request(
    target_service="service1",
    method="get_user",
    params={"user_id": "123"},
    response={"name": "Test User", "email": "test@example.com"}
)

# Set up an exception to be raised
from simple_mas.exceptions import ServiceNotFoundError
mock_comm.expect_request(
    target_service="service2",
    method="get_data",
    params={"id": "456"},
    exception=ServiceNotFoundError("Service not found")
)
```

#### Handling Notifications

```python
# Set up an expected notification
mock_comm.expect_notification(
    target_service="logging_service",
    method="log_event",
    params={"level": "info", "message": "Test event"}
)

# Send a notification
await agent.send_notification(
    target_service="logging_service",
    method="log_event",
    params={"level": "info", "message": "Test event"}
)

# Verify all expectations were met
mock_comm.verify_all_expectations_met()
```

#### Testing Handler Callbacks

```python
# Register a handler in the agent
@agent.handler("process_data")
async def handle_process_data(params):
    return {"processed": params.get("data", "") + "_processed"}

# Trigger the handler directly through the mock communicator
result = await mock_comm.trigger_handler(
    method="process_data",
    params={"data": "test_input"}
)

# Verify the result
assert result == {"processed": "test_input_processed"}
```

#### Checking Call History

```python
# Make some calls through the agent
await agent.send_request(
    target_service="service1",
    method="method1",
    params={"param1": "value1"}
)

await agent.send_notification(
    target_service="service2",
    method="method2",
    params={"param2": "value2"}
)

# Check the call history
assert len(mock_comm.calls) == 2
assert mock_comm.calls[0].method_name == "send_request"
assert mock_comm.calls[0].args[0] == "service1"  # target_service
assert mock_comm.calls[0].args[1] == "method1"   # method
assert mock_comm.calls[0].args[2] == {"param1": "value1"}  # params

assert mock_comm.calls[1].method_name == "send_notification"
assert mock_comm.calls[1].args[0] == "service2"  # target_service
```

### Integration Testing

Test multiple agents communicating:

```python
import pytest
from simple_mas import Agent
from simple_mas.communication.mcp import MCPCommunicator

@pytest.fixture
async def setup_agents():
    # Create agents with MCP for in-memory communication
    agent1 = Agent(
        name="agent1",
        communicator=MCPCommunicator(
            agent_name="agent1",
            service_urls={"agent2": "mcp://agent2"}
        )
    )

    agent2 = Agent(
        name="agent2",
        communicator=MCPCommunicator(
            agent_name="agent2",
            service_urls={"agent1": "mcp://agent1"}
        )
    )

    @agent2.handler("greeting")
    async def handle_greeting(params):
        return {"response": f"Hello, {params.get('name')}!"}

    await agent1.start()
    await agent2.start()

    yield agent1, agent2

    await agent1.stop()
    await agent2.stop()

async def test_agent_communication(setup_agents):
    agent1, agent2 = setup_agents

    # Test communication between agents
    response = await agent1.send_request(
        target_service="agent2",
        method="greeting",
        params={"name": "Agent1"}
    )

    assert response == {"response": "Hello, Agent1!"}
```

## Mocking External Services

```python
import pytest
from unittest.mock import patch, AsyncMock
from simple_mas import Agent
from simple_mas.communication import HTTPCommunicator

@pytest.fixture
async def agent_with_mocked_http():
    with patch("simple_mas.communication.http.aiohttp.ClientSession") as mock_session:
        # Mock the response
        mock_response = AsyncMock()
        mock_response.__aenter__.return_value.status = 200
        mock_response.__aenter__.return_value.json.return_value = {"result": "success"}
        mock_session.return_value.post.return_value = mock_response

        agent = Agent(
            name="test_agent",
            communicator=HTTPCommunicator(
                agent_name="test_agent",
                service_urls={"external": "http://example.com/api"}
            )
        )

        await agent.start()
        yield agent
        await agent.stop()

async def test_external_service(agent_with_mocked_http):
    # Test interaction with mocked external service
    response = await agent_with_mocked_http.send_request(
        target_service="external",
        method="do_something",
        params={"param": "value"}
    )

    assert response == {"result": "success"}
```

## Performance Testing

For performance testing, use the MCP communicator and measure response times:

```python
import time
import statistics
import pytest
from simple_mas import Agent
from simple_mas.communication.mcp import MCPCommunicator

async def test_performance():
    # Create agents for performance testing
    agent1, agent2 = setup_test_agents()

    # Measure response times
    response_times = []
    for _ in range(1000):
        start_time = time.time()
        await agent1.send_request(
            target_service="agent2",
            method="echo",
            params={"message": "test"}
        )
        end_time = time.time()
        response_times.append(end_time - start_time)

    # Analyze results
    avg_time = statistics.mean(response_times)
    p95_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile

    print(f"Average response time: {avg_time:.6f}s")
    print(f"95th percentile response time: {p95_time:.6f}s")
```
