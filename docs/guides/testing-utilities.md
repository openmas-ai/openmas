# Testing Your OpenMAS Applications

OpenMAS provides utilities to help you write robust unit and integration tests for your own multi-agent systems. This guide focuses on how to use these tools: `MockCommunicator` and `AgentTestHarness`.

These utilities allow you to test your agent's logic and interactions in isolation, without needing to run real dependent services or manage complex network setups during testing.

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
    assert mock_communicator.is_handler_registered("greet")

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

The `AgentTestHarness` (`openmas.testing.AgentTestHarness`) builds upon `MockCommunicator` to provide a higher-level way to manage and test one or more agent instances within your tests.

**Key Benefits:**

*   **Lifecycle Management:** Easily create, start (`setup`, `run`), and stop (`shutdown`) agents within tests.
*   **Automatic Mocking:** Automatically creates and injects `MockCommunicator` instances into the agents it manages.
*   **Multi-Agent Testing:** Manages multiple agents and their mock communicators, simplifying the testing of interactions.
*   **Communication Simulation:** Provides helpers to simulate requests *between* agents managed by the harness.

### Basic Single Agent Testing

```python
import pytest
from openmas.testing import AgentTestHarness
from my_project.agents import MyAgent # Your agent class

@pytest.mark.asyncio
asnyc def test_my_agent_behavior():
    harness = AgentTestHarness()

    # Create an agent instance managed by the harness
    # The harness will automatically provide a MockCommunicator
    agent_instance = await harness.create_agent(agent_cls=MyAgent, name="test-agent-1")

    # Get the mock communicator for this agent if needed for expectations
    mock_comm = harness.get_communicator("test-agent-1")
    mock_comm.expect_request(target_service="other", method="ping", response={})

    # Start the agent (runs setup and run in the background)
    async with harness.start_agents():
        # Agent is now running
        # You can interact with it, e.g., by triggering its handlers
        response = await mock_comm.trigger_handler("internal_task", {"data": 123})
        assert response["status"] == "processed"

        # Or simulate requests coming from outside
        # await harness.simulate_external_request("test-agent-1", "some_method", {})

    # Agent is stopped automatically when exiting the 'async with' block

    # Verify communicator expectations
    mock_comm.verify()
```

### Multi-Agent Interaction Testing

This is where `AgentTestHarness` shines.

```python
import pytest
from openmas.testing import AgentTestHarness
from my_project.agents import RequestAgent, WorkerAgent

@pytest.mark.asyncio
async def test_request_worker_interaction():
    harness = AgentTestHarness()

    # Create multiple agents
    requester = await harness.create_agent(agent_cls=RequestAgent, name="requester")
    worker = await harness.create_agent(agent_cls=WorkerAgent, name="worker")

    # Get their mock communicators
    req_comm = harness.get_communicator("requester")
    worker_comm = harness.get_communicator("worker")

    # Set expectations: Requester calls Worker's 'do_work' method
    # Note: Harness automatically routes calls between mocked agents
    worker_comm.expect_handler_call(
        method="do_work",
        params={"task_id": "task-abc"},
        # Define the response the Worker's handler should give
        response={"result": "work complete for task-abc"}
    )

    async with harness.start_agents():
        # Trigger the Requester agent to start the interaction
        # Assuming Requester has a method 'start_task' that calls worker.do_work
        final_result = await req_comm.trigger_handler("start_task", {"id": "task-abc"})

        # Assert the final result received by the requester
        assert final_result == {"status": "success", "worker_result": "work complete for task-abc"}

    # Verify expectations on both communicators
    req_comm.verify()
    worker_comm.verify()

```

By using `MockCommunicator` for single-agent unit tests and `AgentTestHarness` for integration tests (especially multi-agent scenarios), you can build confidence in the correctness of your OpenMAS applications.
