"""Tests for the agent module."""

import asyncio
from unittest import mock

import pytest

from simple_mas.exceptions import LifecycleError

# Import SimpleAgent from conftest.py
from tests.conftest import SimpleAgent


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
    async def test_lifecycle(self, simple_agent, mock_communicator):
        """Test the agent lifecycle."""
        agent = simple_agent

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
    async def test_start_already_running(self, simple_agent):
        """Test that starting an already running agent raises an error."""
        # Start the agent
        await simple_agent.start()

        # Try to start it again
        with pytest.raises(LifecycleError):
            await simple_agent.start()

        # Clean up
        await simple_agent.stop()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, simple_agent, mock_communicator):
        """Test that stopping a non-running agent is a no-op."""
        # Stop the agent (should be a no-op)
        await simple_agent.stop()

        # The shutdown hook should not have been called
        assert not simple_agent.shutdown_called

        # The communicator should not have been stopped
        mock_communicator.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_in_run(self, simple_agent):
        """Test that exceptions in the run method are propagated."""

        # Override the run method to raise an exception
        async def run_with_exception():
            raise ValueError("Test exception")

        # Use patch to replace the run method
        with mock.patch.object(simple_agent, "run", new=run_with_exception):
            # Start the agent
            await simple_agent.start()

            # Wait for the exception to propagate
            with pytest.raises(ValueError, match="Test exception"):
                await simple_agent._task
