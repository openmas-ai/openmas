"""Tests for the agent module."""

import asyncio
from unittest import mock

import pytest

from simple_mas.agent import BaseAgent
from simple_mas.config import AgentConfig
from simple_mas.exceptions import LifecycleError


class SimpleAgent(BaseAgent):
    """A simple agent for testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_called = False
        self.run_called = False
        self.shutdown_called = False
        self.run_duration = 0.1  # seconds

    async def setup(self) -> None:
        """Set up the agent."""
        self.setup_called = True

    async def run(self) -> None:
        """Run the agent."""
        self.run_called = True
        await asyncio.sleep(self.run_duration)

    async def shutdown(self) -> None:
        """Shut down the agent."""
        self.shutdown_called = True


@pytest.fixture
def mock_communicator():
    """Create a mock communicator."""
    communicator = mock.AsyncMock()
    return communicator


@pytest.fixture
def config():
    """Create a test configuration."""
    return AgentConfig(name="test-agent")


class TestBaseAgent:
    """Tests for the BaseAgent class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_communicator, config):
        """Test that initialization sets up the agent correctly."""
        communicator_class = mock.MagicMock(return_value=mock_communicator)

        agent = SimpleAgent(config=config, communicator_class=communicator_class)

        assert agent.name == "test-agent"
        assert agent.config.name == "test-agent"
        assert agent.communicator == mock_communicator
        assert not agent._is_running
        assert agent._task is None

        # The communicator should be initialized with the agent name and service URLs
        communicator_class.assert_called_once_with("test-agent", {})

    @pytest.mark.asyncio
    async def test_lifecycle(self, mock_communicator, config):
        """Test the agent lifecycle."""
        agent = SimpleAgent(config=config)
        agent.communicator = mock_communicator

        # Start the agent
        await agent.start()

        # The agent should be running
        assert agent._is_running
        assert agent._task is not None

        # The setup hook should have been called
        assert agent.setup_called

        # The communicator should have been started
        mock_communicator.start.assert_called_once()

        # Let the agent run for a bit
        await asyncio.sleep(agent.run_duration * 2)

        # The run hook should have been called
        assert agent.run_called

        # Stop the agent
        await agent.stop()

        # The agent should be stopped
        assert not agent._is_running
        assert agent._task is None

        # The shutdown hook should have been called
        assert agent.shutdown_called

        # The communicator should have been stopped
        mock_communicator.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_already_running(self, mock_communicator, config):
        """Test that starting an already running agent raises an error."""
        agent = SimpleAgent(config=config)
        agent.communicator = mock_communicator

        # Start the agent
        await agent.start()

        # Try to start it again
        with pytest.raises(LifecycleError):
            await agent.start()

        # Clean up
        await agent.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, mock_communicator, config):
        """Test that stopping a non-running agent is a no-op."""
        agent = SimpleAgent(config=config)
        agent.communicator = mock_communicator

        # Stop the agent (should be a no-op)
        await agent.stop()

        # The shutdown hook should not have been called
        assert not agent.shutdown_called

        # The communicator should not have been stopped
        mock_communicator.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_in_run(self, mock_communicator, config):
        """Test that exceptions in the run method are propagated."""
        agent = SimpleAgent(config=config)
        agent.communicator = mock_communicator

        # Override the run method to raise an exception
        async def run_with_exception():
            raise ValueError("Test exception")

        # Use patch to replace the run method
        with mock.patch.object(agent, "run", new=run_with_exception):
            # Start the agent
            await agent.start()

            # Wait for the exception to propagate
            with pytest.raises(ValueError, match="Test exception"):
                await agent._task
