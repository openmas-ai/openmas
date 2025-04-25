"""Tests for the BDI agent implementation."""

import asyncio
from typing import Dict
from unittest.mock import AsyncMock, patch

import pytest

from openmas.agent.bdi import BdiAgent
from openmas.config import AgentConfig

# Note: bdi_agent fixture is now imported from conftest.py


class TestBdiAgent:
    """Tests for the BdiAgent class."""

    @pytest.fixture
    def bdi_agent(self):
        """Create a BdiAgent instance for testing."""
        config = AgentConfig(name="test-agent", service_urls={})
        agent = BdiAgent(config=config)
        return agent

    @pytest.mark.asyncio
    async def test_add_belief(self, bdi_agent: BdiAgent) -> None:
        """Test adding a belief to the agent."""
        # Mock the on_belief_change method
        bdi_agent.on_belief_change = AsyncMock()

        # Add a belief
        bdi_agent.add_belief("test_belief", "test_value")

        # Check that the belief was added
        assert bdi_agent.get_belief("test_belief") == "test_value"

        # Give time for the async task to complete
        await asyncio.sleep(0.1)

        # Check that on_belief_change was called
        bdi_agent.on_belief_change.assert_called_once_with("test_belief", "test_value")

    @pytest.mark.asyncio
    async def test_remove_belief(self, bdi_agent: BdiAgent) -> None:
        """Test removing a belief from the agent."""
        # Add a belief
        bdi_agent.add_belief("test_belief", "test_value")

        # Mock the on_belief_change method
        bdi_agent.on_belief_change = AsyncMock()

        # Remove the belief
        bdi_agent.remove_belief("test_belief")

        # Check that the belief was removed
        assert bdi_agent.get_belief("test_belief") is None

        # Give time for the async task to complete
        await asyncio.sleep(0.1)

        # Check that on_belief_change was called
        bdi_agent.on_belief_change.assert_called_once_with("test_belief", None)

    @pytest.mark.asyncio
    async def test_add_desire(self, bdi_agent: BdiAgent) -> None:
        """Test adding a desire to the agent."""
        # Mock the on_desire_change method
        bdi_agent.on_desire_change = AsyncMock()

        # Add a desire
        bdi_agent.add_desire("test_desire")

        # Check that the desire was added
        assert "test_desire" in bdi_agent.get_all_desires()

        # Give time for the async task to complete
        await asyncio.sleep(0.1)

        # Check that on_desire_change was called
        bdi_agent.on_desire_change.assert_called_once_with("test_desire", True)

    @pytest.mark.asyncio
    async def test_remove_desire(self, bdi_agent: BdiAgent) -> None:
        """Test removing a desire from the agent."""
        # Add a desire
        bdi_agent.add_desire("test_desire")

        # Mock the on_desire_change method
        bdi_agent.on_desire_change = AsyncMock()

        # Remove the desire
        bdi_agent.remove_desire("test_desire")

        # Check that the desire was removed
        assert "test_desire" not in bdi_agent.get_all_desires()

        # Give time for the async task to complete
        await asyncio.sleep(0.1)

        # Check that on_desire_change was called
        bdi_agent.on_desire_change.assert_called_once_with("test_desire", False)

    @pytest.mark.asyncio
    async def test_add_intention(self, bdi_agent: BdiAgent) -> None:
        """Test adding an intention to the agent."""
        # Mock the on_intention_change method
        bdi_agent.on_intention_change = AsyncMock()

        # Add an intention
        intention: Dict[str, str] = {"id": "test_intention", "goal": "test_goal"}
        bdi_agent.add_intention(intention)

        # Check that the intention was added
        intentions = bdi_agent.get_all_intentions()
        assert len(intentions) == 1
        assert intentions[0]["id"] == "test_intention"

        # Give time for the async task to complete
        await asyncio.sleep(0.1)

        # Check that on_intention_change was called
        bdi_agent.on_intention_change.assert_called_once_with(intention, True)

    @pytest.mark.asyncio
    async def test_remove_intention(self, bdi_agent: BdiAgent) -> None:
        """Test removing an intention from the agent."""
        # Add an intention
        intention: Dict[str, str] = {"id": "test_intention", "goal": "test_goal"}
        bdi_agent.add_intention(intention)

        # Mock the on_intention_change method
        bdi_agent.on_intention_change = AsyncMock()

        # Remove the intention
        bdi_agent.remove_intention("test_intention")

        # Check that the intention was removed
        assert len(bdi_agent.get_all_intentions()) == 0

        # Give time for the async task to complete
        await asyncio.sleep(0.1)

        # Check that on_belief_change was called
        bdi_agent.on_intention_change.assert_called_once_with(intention, False)

    @pytest.mark.asyncio
    async def test_bdi_cycle_starts_when_agent_runs(self, bdi_agent: BdiAgent) -> None:
        """Test that the BDI cycle starts when the agent runs."""
        # Patch the _run_bdi_cycle method
        with patch.object(bdi_agent, "_run_bdi_cycle", new_callable=AsyncMock) as mock_run_bdi_cycle:
            # Create a task to run the agent
            task = asyncio.create_task(bdi_agent.run())

            # Give time for the agent to start
            await asyncio.sleep(0.1)

            # Cancel the task to stop the agent
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Check that _run_bdi_cycle was called
            mock_run_bdi_cycle.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_bdi_cycle(self, bdi_agent: BdiAgent) -> None:
        """Test that shutdown cancels the BDI cycle."""

        async def dummy_task() -> None:
            try:
                # Just wait forever
                await asyncio.Future()
            except asyncio.CancelledError:
                # Allow the cancel to propagate
                raise

        # Create a real task that we can track
        dummy_future = asyncio.create_task(dummy_task())
        bdi_agent._bdi_task = dummy_future

        # Patch the BaseAgent.shutdown method
        with patch("openmas.agent.base.BaseAgent.shutdown", new_callable=AsyncMock):
            # Call shutdown
            await bdi_agent.shutdown()

            # Verify the task was cancelled
            assert dummy_future.cancelled()

    @pytest.mark.asyncio
    async def test_run_bdi_cycle_calls_lifecycle_methods(self, bdi_agent: BdiAgent) -> None:
        """Test that _run_bdi_cycle calls the BDI lifecycle methods."""
        # Mock the lifecycle methods
        bdi_agent.update_beliefs = AsyncMock()
        bdi_agent.deliberate = AsyncMock()
        bdi_agent.plan = AsyncMock()
        bdi_agent.execute_intentions = AsyncMock()

        # Set a short deliberation cycle interval
        bdi_agent._deliberation_cycle_interval = 0.01

        # Run the BDI cycle for a short time
        task = asyncio.create_task(bdi_agent._run_bdi_cycle())
        await asyncio.sleep(0.1)

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Check that lifecycle methods were called at least once
        assert bdi_agent.update_beliefs.called
        assert bdi_agent.deliberate.called
        assert bdi_agent.plan.called
        assert bdi_agent.execute_intentions.called
