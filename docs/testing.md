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

## Using the AgentTestHarness

SimpleMAS provides a comprehensive test harness specifically designed to make testing agents easier. The `AgentTestHarness` takes care of:

1. Creating agent instances with test configuration
2. Setting up agents with MockCommunicator for intercepting communications
3. Managing agent lifecycle (start/stop) within test contexts
4. Facilitating simulated request handling and assertions

### Basic Usage

```python
import pytest
from simple_mas.agent import Agent
from simple_mas.testing import AgentTestHarness

@pytest.fixture
def agent_harness():
    # Create a harness for the specific agent type
    return AgentTestHarness(
        Agent,  # Agent class to test
        default_config={"name": "test-agent", "service_urls": {}}
    )

@pytest.mark.asyncio
async def test_agent_behavior(agent_harness):
    # Create an agent with the harness
    agent = await agent_harness.create_agent()

    # Start the agent using a context manager
    async with agent_harness.running_agent(agent):
        # Set up an expected external service request
        agent_harness.communicator.expect_request(
            "external-service", "get_data", {"id": "123"}, {"result": "test_data"}
        )

        # Trigger a handler on the agent (simulating an incoming request)
        result = await agent_harness.trigger_handler(
            agent, "process_request", {"params": "value"}
        )

        # Verify the result
        assert result == expected_value

        # Verify that all expected communications occurred
        agent_harness.communicator.verify()
```

### Advanced Features

#### Waiting for Asynchronous Conditions

The harness provides a utility to wait for asynchronous conditions:

```python
@pytest.mark.asyncio
async def test_async_behavior(agent_harness):
    agent = await agent_harness.create_agent()

    async with agent_harness.running_agent(agent):
        # Start some asynchronous operation
        asyncio.create_task(agent.some_async_operation())

        # Wait for a condition to be met with a timeout
        condition_met = await agent_harness.wait_for(
            lambda: getattr(agent, 'operation_complete', False),
            timeout=1.0
        )

        # Verify the condition was met
        assert condition_met is True
        assert agent.operation_complete is True
```

#### Testing Agent Interactions

When testing interactions between multiple agents:

```python
@pytest.mark.asyncio
async def test_agent_interaction():
    # Create harnesses for two different agents
    agent1_harness = AgentTestHarness(Agent1)
    agent2_harness = AgentTestHarness(Agent2)

    # Create agent instances
    agent1 = await agent1_harness.create_agent(name="agent1")
    agent2 = await agent2_harness.create_agent(name="agent2")

    # Configure agent1 to know about agent2
    agent1.communicator.service_urls["agent2"] = "mcp://agent2"

    # Set up the expected request to agent2
    agent2_harness.communicator.expect_request(
        "agent2", "get_info", {"query": "test"}, {"info": "test_result"}
    )

    # Start both agents
    async with agent1_harness.running_agent(agent1), agent2_harness.running_agent(agent2):
        # Trigger a handler on agent1 that will interact with agent2
        result = await agent1_harness.trigger_handler(
            agent1, "process_with_agent2", {"query": "test"}
        )

        # Verify the result
        assert result == {"status": "success", "data": "test_result"}

        # Verify that all expected communications occurred
        agent2_harness.communicator.verify()
```

#### Customizing the Test Agent

For more complex testing scenarios, you can subclass `AgentTestHarness`:

```python
class CustomTestHarness(AgentTestHarness):
    """Custom test harness with additional utilities."""

    async def setup_test_scenario(self, agent):
        """Set up a common test scenario."""
        # Configure the agent for a specific test scenario
        agent.some_property = "test_value"

        # Set up expected communications
        self.communicator.expect_request(
            "service1", "method1", {"param": "value"}, {"result": "response"}
        )

        return agent
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
