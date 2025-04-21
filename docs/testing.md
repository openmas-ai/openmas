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
