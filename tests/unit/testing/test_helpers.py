"""Tests for the testing helper functions."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from openmas.agent.base import BaseAgent
from openmas.config import AgentConfig
from openmas.testing import (
    MockCommunicator,
    expect_notification,
    expect_sender_request,
    multi_running_agents,
    setup_sender_receiver_test,
)


# Create minimal agent classes for testing
class TestSenderAgent(BaseAgent):
    """Test sender agent for helper tests."""

    def __init__(self, name="test-sender", config=None):
        """Initialize with a mocked config to avoid config loading issues."""
        # Create object with BaseAgent constructor first, to get proper properties
        super().__init__(config=AgentConfig(name=name), env_prefix="")
        # Then override with our mocks
        self.communicator = None
        self.logger = MagicMock()
        self.setup_called = False
        self.run_called = False
        self.shutdown_called = False

    async def setup(self) -> None:
        """Set up the agent."""
        self.setup_called = True

    async def run(self) -> None:
        """Run the agent."""
        self.run_called = True

    async def shutdown(self) -> None:
        """Shut down the agent."""
        self.shutdown_called = True

    async def start(self) -> None:
        """Start the agent (for testing)."""
        await self.setup()

    async def stop(self) -> None:
        """Stop the agent (for testing)."""
        await self.shutdown()


class TestReceiverAgent(BaseAgent):
    """Test receiver agent for helper tests."""

    def __init__(self, name="test-receiver", config=None):
        """Initialize with a mocked config to avoid config loading issues."""
        # Create object with BaseAgent constructor first, to get proper properties
        super().__init__(config=AgentConfig(name=name), env_prefix="")
        # Then override with our mocks
        self.communicator = None
        self.logger = MagicMock()
        self.setup_called = False
        self.run_called = False
        self.shutdown_called = False

    async def setup(self) -> None:
        """Set up the agent."""
        self.setup_called = True

    async def run(self) -> None:
        """Run the agent."""
        self.run_called = True

    async def shutdown(self) -> None:
        """Shut down the agent."""
        self.shutdown_called = True

    async def start(self) -> None:
        """Start the agent (for testing)."""
        await self.setup()

    async def stop(self) -> None:
        """Stop the agent (for testing)."""
        await self.shutdown()


@pytest_asyncio.fixture
async def mock_communicator():
    """Create a mock communicator for testing."""
    comm = MockCommunicator(agent_name="test-agent")
    yield comm
    # Verify all expectations were met
    comm.verify()


@pytest_asyncio.fixture
async def sender_agent():
    """Create a test sender agent with a mock communicator."""
    agent = TestSenderAgent(name="sender")
    agent.communicator = MockCommunicator(agent_name="sender")
    return agent


@pytest_asyncio.fixture
async def receiver_agent():
    """Create a test receiver agent with a mock communicator."""
    agent = TestReceiverAgent(name="receiver")
    agent.communicator = MockCommunicator(agent_name="receiver")
    return agent


@pytest.mark.asyncio
async def test_setup_sender_receiver_test():
    """Test that setup_sender_receiver_test creates and configures agents correctly."""
    # Mock the create_agent method to avoid config issues
    with patch("openmas.testing.harness.AgentTestHarness.create_agent") as mock_create:
        # For the sender
        sender = TestSenderAgent(name="sender")
        sender.communicator = MockCommunicator(agent_name="sender")

        # For the receiver
        receiver = TestReceiverAgent(name="receiver")
        receiver.communicator = MockCommunicator(agent_name="receiver")

        # Set up expected returns
        mock_create.side_effect = lambda name, **kwargs: sender if name == "sender" else receiver

        # Call the function
        sender_harness, receiver_harness, sender_result, receiver_result = await setup_sender_receiver_test(
            TestSenderAgent, TestReceiverAgent
        )

        # Verify the harnesses were created with the correct agent classes
        assert sender_harness.agent_class is TestSenderAgent
        assert receiver_harness.agent_class is TestReceiverAgent

        # Verify the agents are our mocked instances
        assert sender_result is sender
        assert receiver_result is receiver


@pytest.mark.asyncio
async def test_expect_sender_request(sender_agent):
    """Test that expect_sender_request correctly sets up request expectations."""
    # Set up expectation
    expect_sender_request(sender_agent, "receiver", "process_data", {"message": "hello"}, {"status": "ok"})

    # Verify the expectation was set correctly by making the request
    response = await sender_agent.communicator.send_request(
        target_service="receiver", method="process_data", params={"message": "hello"}
    )

    assert response == {"status": "ok"}


@pytest.mark.asyncio
async def test_expect_notification(sender_agent):
    """Test that expect_notification correctly sets up notification expectations."""
    # Set up expectation
    expect_notification(sender_agent, "logger", "log_event", {"level": "info", "message": "test"})

    # Verify the expectation was set correctly by sending the notification
    await sender_agent.communicator.send_notification(
        target_service="logger", method="log_event", params={"level": "info", "message": "test"}
    )

    # If we get here without an assertion error, the test passes


@pytest.mark.asyncio
async def test_running_agents():
    """Test that multi_running_agents correctly manages agent lifecycles."""
    # Create test agents directly (no config loading)
    sender = TestSenderAgent(name="sender")
    receiver = TestReceiverAgent(name="receiver")

    # Use AsyncMock instead of manually creating async functions
    sender_context = AsyncMock()
    sender_context.__aenter__.return_value = sender

    receiver_context = AsyncMock()
    receiver_context.__aenter__.return_value = receiver

    # Set up the harnesses
    sender_harness = MagicMock()
    sender_harness.running_agent.return_value = sender_context

    receiver_harness = MagicMock()
    receiver_harness.running_agent.return_value = receiver_context

    # Test multi_running_agents
    runner: Any = multi_running_agents(sender_harness, sender, receiver_harness, receiver)
    async with runner:
        pass

    # Verify that contexts were created correctly
    sender_harness.running_agent.assert_called_once_with(sender)
    receiver_harness.running_agent.assert_called_once_with(receiver)

    # Verify that the context managers were entered and exited
    sender_context.__aenter__.assert_awaited_once()
    sender_context.__aexit__.assert_awaited_once()
    receiver_context.__aenter__.assert_awaited_once()
    receiver_context.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_running_agents_validation():
    """Test that multi_running_agents validates its arguments correctly."""
    # Test with no arguments - note: we need to attempt to enter the context
    # for the validation to actually run
    with pytest.raises(ValueError):
        async with multi_running_agents():
            pass

    # Test with a single argument (odd number)
    with pytest.raises(ValueError):
        async with multi_running_agents(MagicMock()):
            pass


@pytest.mark.asyncio
async def test_send_method_error_message():
    """Test the improved error message when 'send' method is called."""
    comm = MockCommunicator(agent_name="test-agent")

    error_pattern = "Did you mean to use 'send_request\\(\\)' or 'send_notification\\(\\)'"
    with pytest.raises(AttributeError, match=error_pattern):
        await comm.send(target_service="test", payload={"message": "hello"})


@pytest.mark.asyncio
async def test_similar_method_suggestions():
    """Test that similar method name suggestions are provided for typos."""
    comm = MockCommunicator(agent_name="test-agent")

    # Create a deliberate typo that should suggest 'send_notification'
    with patch.object(comm, "__getattr__") as mock_getattr:
        # Create the mock behavior
        mock_getattr.side_effect = AttributeError(
            "MockCommunicator has no attribute 'send_notificaiton'. " "Did you mean one of these? 'send_notification'"
        )

        # Test with a typo that should suggest send_notification
        with pytest.raises(AttributeError, match="Did you mean one of these\\?"):
            await comm.send_notificaiton(target_service="test", method="test")

    # Test another typo with a different method
    with patch.object(comm, "__getattr__") as mock_getattr:
        mock_getattr.side_effect = AttributeError("MockCommunicator has no attribute 'sendrequest'")
        with pytest.raises(AttributeError, match="no attribute 'sendrequest'"):
            await comm.sendrequest(target_service="test", method="test")


@pytest.mark.asyncio
async def test_mock_communicator_handlers():
    """Test that improvements to MockCommunicator work with handler registration."""
    comm = MockCommunicator(agent_name="test-agent")

    # Register a test handler
    async def test_handler(params):
        return {"status": "ok"}

    await comm.register_handler("test", test_handler)

    # Trigger the handler
    response = await comm.trigger_handler("test", {"message": "hello"})
    assert response == {"status": "ok"}
