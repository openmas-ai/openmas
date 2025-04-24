"""Tests for the AgentTestHarness.

This file demonstrates how to use the AgentTestHarness for testing SimpleMAS agents.
"""

import asyncio
from typing import Any, Dict

import pytest

from simple_mas.agent import BaseAgent
from simple_mas.config import AgentConfig
from simple_mas.testing import AgentTestHarness


class SimpleTestAgent(BaseAgent):
    """A simple agent for testing the harness."""

    def __init__(
        self,
        name=None,
        config=None,
        config_model=AgentConfig,
        env_prefix="",
    ):
        """Initialize the simple test agent."""
        super().__init__(name=name, config=config, config_model=config_model, env_prefix=env_prefix)
        self.data_store = {}
        self.processing_history = []

    async def setup(self) -> None:
        """Set up the agent by registering handlers."""
        await super().setup()

        # Register handlers that will be tested
        await self.communicator.register_handler("store_data", self.handle_store_data)
        await self.communicator.register_handler("get_data", self.handle_get_data)
        await self.communicator.register_handler("process_with_external", self.handle_process_with_external)

    async def run(self) -> None:
        """Run the agent's main loop."""
        # For testing purposes, we don't need a real implementation
        # Just wait forever or until cancelled
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            raise

    async def shutdown(self) -> None:
        """Shut down the agent."""
        # Cleanup any resources if needed
        self.logger.debug("Shutting down test agent", agent_name=self.name)
        # Call the parent class shutdown
        await super().shutdown()

    async def handle_store_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Store data in the agent's data store.

        Args:
            params: Must contain 'key' and 'value' keys

        Returns:
            A success message
        """
        key = params.get("key")
        value = params.get("value")

        if not key:
            return {"error": "Missing key parameter"}

        self.data_store[key] = value
        return {"status": "success", "key": key}

    async def handle_get_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve data from the agent's data store.

        Args:
            params: Must contain a 'key' parameter

        Returns:
            The stored data or an error
        """
        key = params.get("key")

        if not key:
            return {"error": "Missing key parameter"}

        if key not in self.data_store:
            return {"error": f"Key '{key}' not found"}

        return {"key": key, "value": self.data_store[key]}

    async def handle_process_with_external(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process data by calling an external service.

        Args:
            params: Contains 'data' to process

        Returns:
            The processed data
        """
        data = params.get("data", "")

        # Call external service to enrich data
        try:
            response = await self.communicator.send_request("enrichment-service", "enrich_data", {"input": data})

            enriched_data = response.get("enriched", f"Enriched: {data}")
            self.processing_history.append(enriched_data)
            return {"result": enriched_data, "status": "success"}

        except Exception as e:
            self.logger.error(f"Error calling external service: {e}")
            return {"error": str(e), "status": "error"}


# Create a test harness specifically for SimpleTestAgent for these tests
@pytest.fixture
def test_agent_harness():
    """Create an AgentTestHarness for testing SimpleTestAgent."""
    # Create the harness with the config
    return AgentTestHarness(SimpleTestAgent, default_config={"name": "test-agent", "service_urls": {}})


class TestAgentHarness:
    """Tests for the AgentTestHarness."""

    @pytest.mark.asyncio
    async def test_basic_agent_functionality(self, test_agent_harness):
        """Test basic agent functionality with the harness."""
        # Create an agent with the harness
        agent = await test_agent_harness.create_agent()

        # Use the context manager to start and stop the agent
        async with test_agent_harness.running_agent(agent):
            # Test the store_data handler
            result1 = await test_agent_harness.trigger_handler(
                agent, "store_data", {"key": "test_key", "value": "test_value"}
            )
            assert result1 == {"status": "success", "key": "test_key"}

            # Test the get_data handler
            result2 = await test_agent_harness.trigger_handler(agent, "get_data", {"key": "test_key"})
            assert result2 == {"key": "test_key", "value": "test_value"}

    @pytest.mark.asyncio
    async def test_agent_with_external_service(self, test_agent_harness):
        """Test agent interaction with an external service."""
        # Create an agent with the harness
        agent = await test_agent_harness.create_agent()

        # Set up the expected external service request/response
        test_agent_harness.communicator.expect_request(
            "enrichment-service", "enrich_data", {"input": "test_data"}, {"enriched": "ENRICHED_TEST_DATA"}
        )

        # Use the context manager to start and stop the agent
        async with test_agent_harness.running_agent(agent):
            # Test the process_with_external handler
            result = await test_agent_harness.trigger_handler(agent, "process_with_external", {"data": "test_data"})

            # Verify the result
            assert result == {"result": "ENRICHED_TEST_DATA", "status": "success"}

            # Verify the agent state was updated
            assert "ENRICHED_TEST_DATA" in agent.processing_history

            # Verify that all expected communications occurred
            test_agent_harness.communicator.verify()

    @pytest.mark.asyncio
    async def test_wait_for_condition(self, test_agent_harness):
        """Test the wait_for utility in the harness."""
        # Create an agent with the harness
        agent = await test_agent_harness.create_agent()

        # Use the context manager to start and stop the agent
        async with test_agent_harness.running_agent(agent):
            # Set up a flag to be changed after a delay
            agent.flag_set = False

            # Start a task that will set the flag after a delay
            async def delayed_set_flag():
                await asyncio.sleep(0.05)
                agent.flag_set = True

            asyncio.create_task(delayed_set_flag())

            # Wait for the flag to be set
            result = await test_agent_harness.wait_for(lambda: agent.flag_set, timeout=0.1)

            # Verify that the wait was successful
            assert result is True
            assert agent.flag_set is True

    @pytest.mark.asyncio
    async def test_wait_for_timeout(self, test_agent_harness):
        """Test the wait_for utility timeout."""
        # Create an agent with the harness
        agent = await test_agent_harness.create_agent()

        # Use the context manager to start and stop the agent
        async with test_agent_harness.running_agent(agent):
            # Set up a condition that will never be met
            agent.flag_set = False

            # Wait for the flag to be set (with a short timeout)
            result = await test_agent_harness.wait_for(lambda: agent.flag_set, timeout=0.05)

            # Verify that the wait timed out
            assert result is False
            assert agent.flag_set is False
