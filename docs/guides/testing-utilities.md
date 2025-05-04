# Testing Your OpenMAS Applications

OpenMAS provides utilities to help you write robust unit and integration tests for your own multi-agent systems. This guide focuses on how to use these tools: `MockCommunicator` and `AgentTestHarness`.

These utilities allow you to test your agent's logic and interactions in isolation, without needing to run real dependent services or manage complex network setups during testing.

## Important Testing Concepts to Understand First

Before diving into the specifics of OpenMAS testing utilities, it's important to understand the core testing approach:

### 1. Expectation-Based Testing (NOT Direct Communication)

When using `MockCommunicator` for testing, you're **not** establishing real communication between agents. Instead, you're:

- Setting up **expectations** for what messages should be sent
- Having your agent code execute and attempt to send those messages
- **Verifying** that the expected messages were sent with the correct parameters

This pattern is different from trying to simulate real message passing between agents. The mock is primarily a validation tool.

### 2. Required Agent Implementation

All agent classes in OpenMAS must implement specific abstract methods from `BaseAgent`:

- `setup()`: Initialize the agent
- `run()`: The main agent logic
- `shutdown()`: Clean up resources

If you don't implement these methods in your agent classes, you'll receive errors when trying to use them with the testing harness.

### 3. Test Harness vs. Direct Agent Creation

There are two main approaches to testing:
- Using `AgentTestHarness` to manage agent lifecycle and provide mocked communicators
- Creating agents directly and manually configuring mocked communicators

The examples below will show both approaches.

## Using `MockCommunicator`

The `MockCommunicator` (`openmas.testing.MockCommunicator`) is a powerful tool for testing individual agents. It acts as a stand-in for a real communicator (like `HttpCommunicator` or `McpSseCommunicator`), allowing you to:

*   Define expected outgoing requests or notifications your agent should send.
*   Simulate incoming responses or errors for those requests.
*   Verify that your agent sent the expected messages.
*   Register mock handlers and trigger them to test your agent's response logic.

### Basic Setup (using `pytest` fixtures)

A common pattern is to create a `pytest` fixture for your mock communicator:

```python
import pytest
from openmas.testing import MockCommunicator

@pytest.fixture
def mock_communicator():
    """Provides a MockCommunicator instance for tests."""
    # Initialize with the name your agent would typically use
    comm = MockCommunicator(agent_name="my-test-agent")
    yield comm
    # Optional: Automatically verify all expectations are met at the end of the test
    comm.verify()
```

You can then inject this fixture into your test functions.

### Setting Expectations and Verifying Requests

You can tell the `MockCommunicator` what `send_request` calls to expect from your agent and what response to return.

```python
from my_project.agents import DataProcessingAgent # Your agent class

@pytest.mark.asyncio
async def test_agent_fetches_user_data(mock_communicator):
    # Instantiate your agent, passing the mock communicator
    # You might need to adapt this based on how your agent gets its communicator
    agent = DataProcessingAgent(name="test-processor", communicator=mock_communicator)

    # 1. Expect the agent to call send_request to 'data-service'
    mock_communicator.expect_request(
        target_service="data-service",
        method="get_user",
        params={"user_id": "123"},
        # Define the response the mock should return
        response={"name": "Test User", "email": "test@example.com"}
    )

    # 2. Run the part of your agent's logic that makes the request
    user_data = await agent.process_user("123") # Assume this method calls send_request

    # 3. Assert based on the mocked response
    assert user_data["name"] == "Test User"
    assert user_data["email"] == "test@example.com"

    # 4. Verify expectations (if not done in the fixture)
    # mock_communicator.verify()
```

### Advanced Parameter Matching

When setting expectations, you don't always need to match parameters exactly. `MockCommunicator` supports flexible matching:

*   **Any Parameters:** Set `params=None` in `expect_request` to match any parameters for that service/method call.
*   **Regex Matching:** Provide a compiled regex object (`re.compile(...)`) as a value in the `params` dictionary to match string parameters against a pattern.
*   **Custom Matcher Functions:** Provide a function as a value in the `params` dictionary. This function will receive the actual parameter value and should return `True` if it matches, `False` otherwise.
*   **Subset Dictionary Matching:** Provide a dictionary for `params`. The actual parameters must contain at least these key-value pairs (extra keys in the actual parameters are ignored).

```python
import re
from openmas.testing import MockCommunicator

@pytest.mark.asyncio
async def test_advanced_matching(mock_communicator):
    # Expect a call to 'process' method with any parameters
    mock_communicator.expect_request(
        target_service="worker-service", method="process", params=None, response={}
    )

    # Expect a call where 'item_id' matches a pattern
    mock_communicator.expect_request(
        target_service="inventory", method="get_item",
        params={"item_id": re.compile(r"ITEM-\d{4}")}, response={}
    )

    # Expect a call where 'quantity' is positive
    def is_positive(val): return isinstance(val, int) and val > 0
    mock_communicator.expect_request(
        target_service="orders", method="place_order",
        params={"item_id": "ABC", "quantity": is_positive}, response={}
    )

    # Expect a call with a nested structure (only checks 'profile.id')
    mock_communicator.expect_request(
        target_service="users", method="update_user",
        params={"user": {"profile": {"id": 123}}}, response={}
    )

    # --- Code that triggers the agent to make these calls ---
    # await agent.do_work_any()
    # await agent.fetch_item("ITEM-1234")
    # await agent.create_order("ABC", 5)
    # await agent.save_user_profile(123, {"name": "Test", "extra": "data"})

    mock_communicator.verify()
```

### Testing Notifications (`send_notification`)

Testing outgoing notifications is similar to requests, but you don't expect a response.

```python
@pytest.mark.asyncio
async def test_agent_sends_event_notification(mock_communicator, agent):
    # Expect the agent to send a notification
    mock_communicator.expect_notification(
        target_service="logging-service",
        method="log_event",
        params={"level": "info", "message": "Processing complete for user X"}
    )

    # Run agent logic that triggers the notification
    await agent.finish_processing("user X")

    # Verify
    mock_communicator.verify()
```

### Testing Handlers (`register_handler`)

You can test if your agent correctly registers handlers and how those handlers behave when triggered.

```python
@pytest.mark.asyncio
async def test_agent_registers_and_handles_greet(mock_communicator, agent):
    # 1. Run the agent's setup logic (which should call register_handler)
    await agent.setup()

    # 2. Check if the handler was registered
    assert "greet" in mock_communicator._handlers  # Access internal _handlers dict

    # 3. Trigger the registered handler with test data
    # This simulates an incoming request to the agent's 'greet' method
    response = await mock_communicator.trigger_handler(
        method="greet",
        params={"name": "Tester"}
    )

    # 4. Assert the response returned by the agent's handler
    assert response == {"message": "Hello, Tester!"}

    # No verify needed here unless other expectations were set
```

### Testing Error Conditions

You can configure the `MockCommunicator` to simulate errors when your agent makes requests.

```python
import pytest
from openmas.exceptions import ServiceNotFoundError, CommunicationError

@pytest.mark.asyncio
async def test_agent_handles_service_not_found(mock_communicator, agent):
    # Expect a request, but configure it to raise an exception
    mock_communicator.expect_request_exception(
        target_service="nonexistent-service",
        method="get_info",
        params={},
        exception=ServiceNotFoundError("Service 'nonexistent-service' not found")
    )

    # Use pytest.raises to assert that the agent's call triggers the expected exception
    with pytest.raises(ServiceNotFoundError):
        await agent.fetch_info_from_nonexistent_service()

    mock_communicator.verify()
```

## Using `AgentTestHarness`

The `AgentTestHarness` (`openmas.testing.AgentTestHarness`) builds upon `MockCommunicator` to provide a higher-level way to manage and test agents within your tests.

**Key Benefits:**

*   **Lifecycle Management:** Easily create, start (`setup`, `run`), and stop (`shutdown`) agents within tests.
*   **Automatic Mocking:** Automatically creates and injects `MockCommunicator` instances into the agents it manages.
*   **Multi-Agent Testing:** Manages multiple agents and their mock communicators, simplifying the testing of interactions.

### Important Notes About AgentTestHarness

1. **Agent Class Requirements**: `AgentTestHarness` requires you to pass the agent class, not an instance. The harness will create instances for you. Your agent class must implement all abstract methods from `BaseAgent` (`setup`, `run`, `shutdown`).

2. **No Automatic Agent Linking**: The harness doesn't automatically establish communication between agents. You must set up appropriate expectations for each agent's communicator.

3. **Using Expectations Not Direct Communication**: Remember that you're testing with expectations rather than real communication. This means setting up what messages you expect agents to send, not trying to make them talk to each other directly.

### Basic Single Agent Testing

```python
import pytest
from openmas.testing import AgentTestHarness
from my_project.agents import MyAgent # Your agent class

@pytest.mark.asyncio
async def test_my_agent_behavior():
    # Create a harness for the agent class
    harness = AgentTestHarness(MyAgent)

    # Create an agent instance (with a mock communicator)
    agent = await harness.create_agent(name="test-agent")

    # Set up expectations for messages the agent will send
    agent.communicator.expect_request(
        target_service="data-service",
        method="get_data",
        params={"id": "12345"},
        response={"data": "test result"}
    )

    # Use the running_agent context manager to manage lifecycle
    async with harness.running_agent(agent):
        # The agent is now set up and running

        # Trigger some behavior that causes the agent to send a request
        await agent.process_item("12345")

        # Verify that the expected communication happened
        agent.communicator.verify()

        # Make assertions about the agent's state
        assert agent.processed_items == ["12345"]
```

## Simplified Multi-Agent Testing Helpers

OpenMAS provides several helper utilities to make multi-agent testing easier and more concise. These utilities are particularly useful for common testing patterns like testing communication between a sender and receiver agent.

### Setting Up Sender-Receiver Tests

The `setup_sender_receiver_test` function simplifies creating a pair of connected test agents:

```python
import pytest
from openmas.testing import setup_sender_receiver_test, expect_sender_request, multi_running_agents

@pytest.mark.asyncio
async def test_sender_receiver_communication():
    # Create both agents with a single call
    sender_harness, receiver_harness, sender, receiver = await setup_sender_receiver_test(
        SenderAgent, ReceiverAgent
    )

    # Set up expectations for the sender's communication
    expect_sender_request(
        sender,
        "receiver",  # target agent name
        "process_data",  # method to call
        {"message": "hello"},  # expected parameters
        {"status": "ok", "processed": True}  # response to return
    )

    # Run both agents in a single context manager
    async with multi_running_agents(sender_harness, sender, receiver_harness, receiver):
        # Trigger the sender's logic
        await sender.send_message("hello")

        # Verify expectations were met
        sender.communicator.verify()
```

### Setting Message Expectations

Instead of directly calling `agent.communicator.expect_request()`, you can use these more intuitive helper functions:

```python
from openmas.testing import expect_sender_request, expect_notification

# Set up a request expectation
expect_sender_request(
    agent,  # the agent that will send the request
    "target-service",  # name of the target service/agent
    "method-name",  # method to call
    {"param1": "value1"},  # expected parameters
    {"result": "success"}  # response to return
)

# Set up a notification expectation
expect_notification(
    agent,  # the agent that will send the notification
    "logger-service",  # target service
    "log_event",  # notification method
    {"level": "info", "message": "test"}  # expected parameters
)
```

### Running Multiple Agents

The `multi_running_agents` function provides a single context manager for running multiple agents:

```python
from openmas.testing import multi_running_agents

# Instead of nested context managers:
# async with harness1.running_agent(agent1):
#     async with harness2.running_agent(agent2):
#         # test code here

# Use the simpler multi_running_agents:
async with multi_running_agents(harness1, agent1, harness2, agent2, harness3, agent3):
    # All agents are now running

    # Trigger agent behavior
    await agent1.do_something()

    # Verify expectations
    agent1.communicator.verify()
    agent2.communicator.verify()
    agent3.communicator.verify()
```

### Complete Multi-Agent Test Example

Here's a complete example showing how the helpers simplify multi-agent testing:

```python
import pytest
from openmas.testing import (
    setup_sender_receiver_test,
    expect_sender_request,
    multi_running_agents
)
from my_project.agents import DataSenderAgent, DataProcessorAgent

@pytest.mark.asyncio
async def test_data_processing_flow():
    # Set up sender and receiver agents
    sender_harness, processor_harness, sender, processor = await setup_sender_receiver_test(
        DataSenderAgent, DataProcessorAgent,
        sender_name="data-sender",
        receiver_name="data-processor"
    )

    # Set up expectations for the communication
    expect_sender_request(
        sender,
        "data-processor",
        "process_data",
        {"data": {"id": "123", "value": "test"}},
        {"status": "processed", "result": "SUCCESS"}
    )

    # Run both agents
    async with multi_running_agents(sender_harness, sender, processor_harness, processor):
        # Trigger the sender to send data
        await sender.send_data_item("123", "test")

        # Verify the communication happened as expected
        sender.communicator.verify()

        # Check agent state if needed
        assert sender.sent_items == ["123"]
        assert processor.processed_items == ["123"]
```

## Best Practices for Testing Multi-Agent Systems

When testing OpenMAS multi-agent systems, especially with mocked communicators, consider these best practices:

1. **Keep Tests Focused**: Test one specific interaction or behavior in each test case.

2. **Separate Unit vs. Integration Tests**: Use `MockCommunicator` for unit tests of individual agents, and real communicators (or a mix of real and mock) for integration tests.

3. **Use Helper Functions**: Leverage the helper functions (`setup_sender_receiver_test`, `expect_sender_request`, etc.) for cleaner, more maintainable test code.

4. **Prefer Clear Expectations**: Set specific expectations rather than using `params=None` when possible, to catch bugs in parameter handling.

5. **Verify All Communicators**: Remember to call `verify()` on every mock communicator to ensure all expected communications happened.

6. **Test Error Handling**: Use `expect_request_exception` to verify your agents handle errors gracefully.

7. **Lifecycle Management**: Use `running_agents` (or `harness.running_agent`) to properly manage agent lifecycle, ensuring `setup`, `run`, and `shutdown` methods are called.

8. **Check for Clear Error Messages**: If you expect a test to fail, assert on the specific error message rather than just the error type. This helps maintain helpful error reporting.

By following these patterns, you can build robust tests for your OpenMAS agents that are easier to maintain and provide better verification of your system's behavior.

## Choosing the Right Testing Approach

OpenMAS provides different levels of testing utilities, from low-level mocks to high-level helpers. Here's how to choose which approach is right for your needs:

### Helper Functions (Highest Level)

**Examples:** `setup_sender_receiver_test`, `expect_sender_request`, `multi_running_agents`

**Best for:**
- Quick setup of standard sender-receiver test scenarios
- Minimal boilerplate code
- Clear, readable tests
- Most common testing patterns

```python
# Example using helper functions
sender_harness, receiver_harness, sender, receiver = await setup_sender_receiver_test(
    SenderAgent, ReceiverAgent
)
expect_sender_request(sender, "receiver", "process", params, response)
async with multi_running_agents(sender_harness, sender, receiver_harness, receiver):
    await sender.run()
```

### AgentTestHarness (Middle Level)

**Best for:**
- Custom agent configurations
- Non-standard test scenarios
- When you need more control over agent lifecycle
- Testing agents individually

```python
# Example using AgentTestHarness directly
harness = AgentTestHarness(MyAgent)
agent = await harness.create_agent(name="test-agent", config={"custom": True})
# Set up expectations manually
agent.communicator.expect_request(...)
async with harness.running_agent(agent):
    await agent.custom_method()
```

### MockCommunicator (Low Level)

**Best for:**
- Complex mocking scenarios
- Custom parameter matching
- Testing handler behavior directly
- When you need maximum control over mocking

```python
# Example using MockCommunicator directly
communicator = MockCommunicator(agent_name="test")
# Attach to an agent manually
agent.communicator = communicator
# Advanced expectation setup
communicator.expect_request(
    target_service="service",
    method="operation",
    params={"id": re.compile(r"\d+")},  # Regex matching
    response={"result": "data"}
)
```

### Decision Table

| If you need to... | Use this approach |
|-------------------|-------------------|
| Test a simple sender-receiver pattern | Helper functions (`setup_sender_receiver_test`, etc.) |
| Run multiple agents in a test | `multi_running_agents` |
| Configure agents with custom settings | Direct `AgentTestHarness` |
| Test complex parameter matching | Direct `MockCommunicator` |
| Assert agent state changes | Direct `AgentTestHarness` |
| Trigger handlers directly | Direct `MockCommunicator.trigger_handler()` |

## Testing MCP Agents

### Testing MCP stdio Tools

Testing agents that use the `McpStdioCommunicator` requires some special considerations, as it involves process management and stdin/stdout communication. Here are the recommended approaches:

#### Unit Testing with Mock Communicator

For unit tests, you can mock the `McpStdioCommunicator` to avoid spawning real processes:

```python
import pytest
from unittest import mock
from openmas.agent import BaseAgent
from openmas.communication.mcp import McpStdioCommunicator

class ToolUserAgent(BaseAgent):
    # Agent implementation...
    pass

@pytest.fixture
def mock_stdio_communicator():
    """Create a mocked stdio communicator."""
    communicator = mock.AsyncMock(spec=McpStdioCommunicator)

    # Mock the call_tool method to return a predefined result
    async def mock_call_tool(target_service, tool_name, arguments):
        if tool_name == "process_data" and "text" in arguments:
            text = arguments["text"]
            return {
                "processed_text": text.upper(),
                "word_count": len(text.split()),
                "status": "success"
            }
        return {"status": "error", "error": "Unknown tool or invalid arguments"}

    communicator.call_tool.side_effect = mock_call_tool
    return communicator

@pytest.mark.asyncio
async def test_tool_user_with_mock_communicator(mock_stdio_communicator):
    """Test the tool user agent with a mock communicator."""
    agent = ToolUserAgent(name="test-agent")
    agent.set_communicator(mock_stdio_communicator)

    await agent.setup()
    await agent.run()

    # Verify the tool was called with expected arguments
    mock_stdio_communicator.call_tool.assert_called_once()
    call_args = mock_stdio_communicator.call_tool.call_args[1]
    assert call_args["tool_name"] == "process_data"
    assert "text" in call_args["arguments"]
```

#### Integration Testing with Standalone Scripts

For integration testing, create a standalone MCP server script that implements the tool functionality:

```python
import asyncio
import json
import sys
import tempfile
import os
from pathlib import Path
from mcp.server.fastmcp import Context, FastMCP

def create_tool_server_script() -> str:
    """Create a standalone MCP server script for testing."""
    return """
#!/usr/bin/env python

import asyncio
import json
import sys
from mcp.server.fastmcp import Context, FastMCP

# Create the server
server = FastMCP("TestToolServer")

@server.tool("process_data", description="Process incoming data")
async def process_data(context: Context, text: str = "") -> str:
    # Process the data
    if text:
        processed_text = text.upper()
        word_count = len(text.split())

        result = {
            "processed_text": processed_text,
            "word_count": word_count,
            "status": "success"
        }
    else:
        result = {
            "error": "No text provided",
            "status": "error"
        }

    # Return JSON string
    return json.dumps(result)

# Run the server
asyncio.run(server.run_stdio_async())
"""

@pytest.mark.asyncio
@pytest.mark.integration
async def test_real_mcp_stdio_tool_call():
    """Test real MCP stdio tool calls with a standalone server script."""
    # Create the server script
    script_content = create_tool_server_script()

    # Write the script to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(script_content)
        script_path = tmp.name

    # Make it executable
    os.chmod(script_path, 0o755)

    # Process handle for cleanup
    process = None

    try:
        from openmas.agent import BaseAgent
        from openmas.communication.mcp import McpStdioCommunicator

        # Create a tool user agent
        agent = BaseAgent(name="test-tool-user")

        # Configure the communicator to use the script
        communicator = McpStdioCommunicator(
            agent_name=agent.name,
            server_mode=False,
            service_urls={
                "test_tool_server": f"stdio:{sys.executable} {script_path}"
            }
        )
        agent.set_communicator(communicator)

        # Call the tool
        await agent.setup()

        # Test the tool call
        result = await communicator.call_tool(
            target_service="test_tool_server",
            tool_name="process_data",
            arguments={"text": "Hello, test!"}
        )

        # Verify the result
        assert result["status"] == "success"
        assert result["processed_text"] == "HELLO, TEST!"
        assert result["word_count"] == 2

    finally:
        # Clean up
        if process and process.returncode is None:
            try:
                process.terminate()
                await asyncio.sleep(0.5)
                if process.returncode is None:
                    process.kill()
            except Exception:
                pass

        # Clean up the temp file
        try:
            os.unlink(script_path)
        except Exception:
            pass
```

#### Testing Timeout Handling

Properly testing timeout handling is important for robust MCP stdio communication:

```python
@pytest.mark.asyncio
@pytest.mark.integration
async def test_timeout_handling():
    """Test timeout handling with MCP stdio tool calls."""
    # Create a script that implements a slow tool
    slow_tool_script = """
#!/usr/bin/env python

import asyncio
import json
import sys
from mcp.server.fastmcp import Context, FastMCP

server = FastMCP("SlowToolServer")

@server.tool("slow_process", description="A tool that takes a long time")
async def slow_process(context: Context, text: str = "") -> str:
    # Simulate a slow operation
    await asyncio.sleep(10.0)  # Sleep for 10 seconds

    result = {
        "processed_text": text.upper(),
        "status": "success"
    }
    return json.dumps(result)

asyncio.run(server.run_stdio_async())
"""

    # Write the script to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(slow_tool_script)
        script_path = tmp.name

    # Make it executable
    os.chmod(script_path, 0o755)

    try:
        from openmas.agent import BaseAgent
        from openmas.communication.mcp import McpStdioCommunicator

        # Create a tool user agent
        agent = BaseAgent(name="test-timeout-user")

        # Configure the communicator
        communicator = McpStdioCommunicator(
            agent_name=agent.name,
            server_mode=False,
            service_urls={
                "slow_tool_server": f"stdio:{sys.executable} {script_path}"
            }
        )
        agent.set_communicator(communicator)

        # Set up the agent
        await agent.setup()

        # Call the slow tool with a short timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                communicator.call_tool(
                    target_service="slow_tool_server",
                    tool_name="slow_process",
                    arguments={"text": "This should time out"}
                ),
                timeout=2.0  # 2-second timeout (shorter than the 10-second sleep)
            )

    finally:
        # Clean up the temp file
        try:
            os.unlink(script_path)
        except Exception:
            pass
```

#### Best Practices for Testing MCP stdio

1. **Use temporary files** for server scripts to avoid leaving artifacts
2. **Clean up processes** explicitly to avoid orphaned processes
3. **Implement proper timeout handling** in both tests and production code
4. **Capture stderr output** from subprocesses for better debugging
5. **Test both success and error cases** to ensure robust error handling
6. **Use mocks for unit tests** and real processes for integration tests
7. **Include process management edge cases** in your test suite
