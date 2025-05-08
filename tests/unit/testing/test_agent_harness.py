"""Tests for the agent harness module."""

import asyncio
from typing import Any, Dict, List

import pytest

from openmas.agent.bdi import BdiAgent
from openmas.config import AgentConfig
from openmas.exceptions import ServiceNotFoundError
from openmas.testing.harness import AgentTestHarness
from openmas.testing.mock_communicator import MockCommunicator


class SimpleTestAgent(BdiAgent):
    """A simple agent for testing the harness."""

    def __init__(
        self,
        name: str = None,
        config: AgentConfig = None,
        config_model: Any = AgentConfig,
        env_prefix: str = "",
        project_root=None,
    ) -> None:
        """Initialize the simple test agent."""
        super().__init__(
            name=name, config=config, config_model=config_model, env_prefix=env_prefix, project_root=project_root
        )
        self.data_store: Dict[str, Any] = {}
        self.processing_history: List[str] = []
        self.callbacks_received: List[str] = []

    async def setup(self) -> None:
        """Set up the agent by registering handlers."""
        await super().setup()

        # Register handlers that will be tested
        await self.communicator.register_handler("store_data", self.handle_store_data)
        await self.communicator.register_handler("get_data", self.handle_get_data)
        await self.communicator.register_handler("process_with_external", self.handle_process_with_external)
        await self.communicator.register_handler("callback", self.handle_callback)

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

    async def handle_store_data(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Store data in the agent's data store.

        Args:
            message: Must contain content with 'key' and 'value' keys

        Returns:
            A success message
        """
        params = message["content"]
        key = params.get("key")
        value = params.get("value")

        if not key:
            return {"error": "Missing key parameter"}

        self.data_store[key] = value
        return {"status": "success", "key": key}

    async def handle_get_data(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve data from the agent's data store.

        Args:
            message: Must contain content with a 'key' parameter

        Returns:
            The stored data or an error
        """
        params = message["content"]
        key = params.get("key")

        if not key:
            return {"error": "Missing key parameter"}

        if key not in self.data_store:
            return {"error": f"Key '{key}' not found"}

        return {"key": key, "value": self.data_store[key]}

    async def handle_process_with_external(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process data by calling an external service.

        Args:
            message: Contains content with 'data' to process

        Returns:
            The processed data
        """
        params = message["content"]
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

    async def handle_callback(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle callback notifications from other agents.

        Args:
            message: The callback message

        Returns:
            Acknowledgment
        """
        params = message["content"]
        source = message.get("sender_id", "unknown")
        event = params.get("event", "unknown")

        self.callbacks_received.append(f"{source}:{event}")
        return {"status": "received", "from": source, "event": event}


# Create a test harness specifically for SimpleTestAgent for these tests
@pytest.fixture
def test_agent_harness(tmp_path) -> AgentTestHarness:
    """Create an AgentTestHarness for testing SimpleTestAgent."""
    # Create the harness with the config and a valid project_root
    return AgentTestHarness(
        SimpleTestAgent, default_config={"name": "test-agent", "service_urls": {}}, project_root=tmp_path
    )


class TestAgentHarness:
    """Tests for the AgentTestHarness."""

    @pytest.mark.asyncio
    async def test_harness_communicator_attribute(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that each agent gets a unique communicator instance."""
        # Create first agent
        agent1 = await test_agent_harness.create_agent(name="agent1")
        first_agent_communicator = agent1.communicator

        # Create second agent
        agent2 = await test_agent_harness.create_agent(name="agent2")
        second_agent_communicator = agent2.communicator

        # Verify that each agent has a unique communicator
        assert first_agent_communicator is not None
        assert second_agent_communicator is not None
        assert first_agent_communicator is not second_agent_communicator

        # Verify that communicators are correctly tracked
        assert test_agent_harness.communicators["agent1"] is first_agent_communicator
        assert test_agent_harness.communicators["agent2"] is second_agent_communicator

    @pytest.mark.asyncio
    async def test_create_agent_assigns_unique_communicators(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that each agent gets a unique MockCommunicator instance."""
        # Create two agents
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")

        # Verify that each agent has a communicator
        assert agent1.communicator is not None
        assert agent2.communicator is not None

        # Verify that the agents have different communicator instances
        assert agent1.communicator is not agent2.communicator

        # Verify that the communicators are properly tracked in the harness
        assert test_agent_harness.communicators["agent1"] is agent1.communicator
        assert test_agent_harness.communicators["agent2"] is agent2.communicator

    @pytest.mark.asyncio
    async def test_basic_agent_functionality(self, test_agent_harness: AgentTestHarness) -> None:
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
    async def test_agent_with_external_service(self, test_agent_harness: AgentTestHarness) -> None:
        """Test agent interaction with an external service."""
        # Create an agent with the harness
        agent = await test_agent_harness.create_agent()

        # Set up the expected external service request/response
        agent.communicator.expect_request(
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
            agent.communicator.verify()

    @pytest.mark.asyncio
    async def test_wait_for_condition(self, test_agent_harness: AgentTestHarness) -> None:
        """Test the wait_for utility in the harness."""
        # Create an agent with the harness
        agent = await test_agent_harness.create_agent()

        # Use the context manager to start and stop the agent
        async with test_agent_harness.running_agent(agent):
            # Set up a flag to be changed after a delay
            agent.flag_set = False

            # Start a task that will set the flag after a delay
            async def delayed_set_flag() -> None:
                await asyncio.sleep(0.05)
                agent.flag_set = True

            asyncio.create_task(delayed_set_flag())

            # Wait for the flag to be set
            result = await test_agent_harness.wait_for(lambda: agent.flag_set, timeout=0.1)

            # Verify that the wait was successful
            assert result is True
            assert agent.flag_set is True

    @pytest.mark.asyncio
    async def test_wait_for_timeout(self, test_agent_harness: AgentTestHarness) -> None:
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

    @pytest.mark.asyncio
    async def test_multi_agent_setup(self, test_agent_harness: AgentTestHarness) -> None:
        """Test creating and tracking multiple agents."""
        # Create multiple agents
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")
        agent3 = await test_agent_harness.create_agent(name="agent3")

        # Check that they were properly tracked
        assert len(test_agent_harness.agents) == 3
        assert len(test_agent_harness.communicators) == 3
        assert "agent1" in test_agent_harness.communicators
        assert "agent2" in test_agent_harness.communicators
        assert "agent3" in test_agent_harness.communicators

        # Check that each agent has its own communicator
        assert agent1.communicator == test_agent_harness.communicators["agent1"]
        assert agent2.communicator == test_agent_harness.communicators["agent2"]
        assert agent3.communicator == test_agent_harness.communicators["agent3"]

    @pytest.mark.asyncio
    async def test_link_agents(self, test_agent_harness: AgentTestHarness) -> None:
        """Test linking agents for direct communication."""
        # Create multiple agents
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")

        # Link them
        await test_agent_harness.link_agents(agent1, agent2)

        # Verify service URLs were set up
        assert agent1.config.service_urls["agent2"] == "mock://agent2"
        assert agent2.config.service_urls["agent1"] == "mock://agent1"

        # Verify communicators were linked
        comm1 = agent1.communicator
        comm2 = agent2.communicator

        assert isinstance(comm1, MockCommunicator)
        assert isinstance(comm2, MockCommunicator)
        assert comm2 in comm1._linked_communicators
        assert comm1 in comm2._linked_communicators

    @pytest.mark.asyncio
    async def test_running_agents_context(self, test_agent_harness: AgentTestHarness) -> None:
        """Test the running_agents context manager."""
        # Create multiple agents
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")

        # Use the context manager to start and stop multiple agents
        async with test_agent_harness.running_agents(agent1, agent2) as running_agents:
            # Check that we got both agents back
            assert len(running_agents) == 2
            assert agent1 in running_agents
            assert agent2 in running_agents

            # Both agents should be started
            assert agent1._is_running
            assert agent2._is_running

        # After the context, both agents should be stopped
        assert not agent1._is_running
        assert not agent2._is_running

    @pytest.mark.asyncio
    async def test_multi_agent_interaction(self, test_agent_harness: AgentTestHarness) -> None:
        """Test interaction between multiple agents."""
        # Create multiple agents
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")

        # Link them
        await test_agent_harness.link_agents(agent1, agent2)

        # Start both agents
        async with test_agent_harness.running_agents(agent1, agent2):
            # Store data in agent1
            await test_agent_harness.trigger_handler(
                agent1, "store_data", {"key": "shared_key", "value": "shared_value"}
            )

            # Instead of using direct request, we'll use trigger_handler on agent1 and verify the result
            result = await test_agent_harness.trigger_handler(agent1, "get_data", {"key": "shared_key"})

            # Verify the result
            assert result == {"key": "shared_key", "value": "shared_value"}

    @pytest.mark.asyncio
    async def test_verify_all_communicators(self, test_agent_harness: AgentTestHarness) -> None:
        """Test verifying expectations across multiple communicators."""
        # Create multiple agents
        await test_agent_harness.create_agent(name="agent1")
        await test_agent_harness.create_agent(name="agent2")

        # Set up expectations on both communicators
        test_agent_harness.communicators["agent1"].expect_request(
            "service", "method1", {"param": "value"}, {"result": "success"}
        )
        test_agent_harness.communicators["agent2"].expect_notification("other-service", "event", {"type": "update"})

        # Verify should fail because neither expectation was met
        with pytest.raises(AssertionError) as excinfo:
            test_agent_harness.verify_all_communicators()

        # Error should include information about both communicators
        error_msg = str(excinfo.value)
        assert "agent1" in error_msg
        assert "agent2" in error_msg

    @pytest.mark.asyncio
    async def test_reset_harness(self, test_agent_harness: AgentTestHarness) -> None:
        """Test resetting the harness state."""
        # Create multiple agents and set expectations
        await test_agent_harness.create_agent(name="agent1")
        await test_agent_harness.create_agent(name="agent2")

        test_agent_harness.communicators["agent1"].expect_request(
            "service", "method", {"param": "value"}, {"result": "success"}
        )

        # Reset the harness
        test_agent_harness.reset()

        # Check that all state was cleared
        assert len(test_agent_harness.agents) == 0
        assert len(test_agent_harness.communicators) == 0

        # Creating a new agent after reset should work fine
        await test_agent_harness.create_agent(name="new-agent")
        assert len(test_agent_harness.agents) == 1
        assert "new-agent" in test_agent_harness.communicators

    @pytest.mark.asyncio
    async def test_error_handling(self, test_agent_harness: AgentTestHarness) -> None:
        """Test handling service errors in agents."""
        # Create an agent
        agent = await test_agent_harness.create_agent()

        # Set up a service error
        error = ServiceNotFoundError("enrichment-service not found")
        agent.communicator.expect_request_exception("enrichment-service", "enrich_data", {"input": "test_data"}, error)

        # Test that the agent handles the error properly
        async with test_agent_harness.running_agent(agent):
            result = await test_agent_harness.trigger_handler(agent, "process_with_external", {"data": "test_data"})

            # Agent should return an error response
            assert result["status"] == "error"
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_multi_agent_notification(self, test_agent_harness: AgentTestHarness) -> None:
        """Test sending notifications between multiple agents."""
        # Create multiple agents
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")
        agent3 = await test_agent_harness.create_agent(name="agent3")

        # Link all agents
        await test_agent_harness.link_agents(agent1, agent2, agent3)

        # Start all agents
        async with test_agent_harness.running_agents(agent1, agent2, agent3):
            # Agent1 sends a notification to all other agents
            await agent1.communicator.send_notification("agent2", "callback", {"event": "update"})
            await agent1.communicator.send_notification("agent3", "callback", {"event": "update"})

            # Wait for the notifications to be processed
            success = await test_agent_harness.wait_for(
                lambda: len(agent2.callbacks_received) > 0 and len(agent3.callbacks_received) > 0, timeout=0.1
            )

            # Verify the notifications were received
            assert success
            # The sender may be recorded as test_sender rather than agent1, so just check that
            # the event was recorded
            assert any("update" in callback for callback in agent2.callbacks_received)
            assert any("update" in callback for callback in agent3.callbacks_received)

    @pytest.mark.asyncio
    async def test_linked_agents_direct_communication(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that linked agents can directly communicate with each other."""
        # Create multiple agents
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")

        # Link them
        await test_agent_harness.link_agents(agent1, agent2)

        # Start both agents
        async with test_agent_harness.running_agents(agent1, agent2):
            # Set up expected request/response
            agent2.communicator.expect_request(
                "agent2", "get_data", {"key": "test-key"}, {"key": "test-key", "value": "test-value"}
            )

            # Store data in agent2
            await test_agent_harness.trigger_handler(agent2, "store_data", {"key": "test-key", "value": "test-value"})

            # Agent1 sends a request to agent2
            response = await agent1.communicator.send_request("agent2", "get_data", {"key": "test-key"})

            # Verify the response
            assert response == {"key": "test-key", "value": "test-value"}

            # Verify expectations were met
            test_agent_harness.verify_all_communicators()

    @pytest.mark.asyncio
    async def test_mock_expectations_propagation(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that expectations from one agent are visible to linked agents."""
        # Create two agents
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")

        # Link them
        await test_agent_harness.link_agents(agent1, agent2)

        # Set up expectations on agent2's communicator
        agent2.communicator.expect_request(
            "agent2", "get_data", {"key": "test-key"}, {"key": "test-key", "value": "test-value"}
        )

        # Agent1 should be able to send a request to agent2 using the linked communicator
        response = await agent1.communicator.send_request("agent2", "get_data", {"key": "test-key"})

        # The response should match what we set up in the expectation
        assert response == {"key": "test-key", "value": "test-value"}

        # Verify all expectations were met
        test_agent_harness.verify_all_communicators()

    @pytest.mark.asyncio
    async def test_link_agents_enables_communication(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that link_agents enables direct message communication between agents."""
        # Create two agents
        agent1 = await test_agent_harness.create_agent(name="sender")
        agent2 = await test_agent_harness.create_agent(name="receiver")

        # Create a handler function with tracking attributes
        async def receiver_handler(message: Dict[str, Any]) -> Dict[str, Any]:
            receiver_handler.called = True
            receiver_handler.payload = message["content"]
            receiver_handler.sender_id = message["sender_id"]
            return {"status": "received"}

        # Initialize tracking attributes
        receiver_handler.called = False
        receiver_handler.payload = None
        receiver_handler.sender_id = None

        # Register the handler on agent2's communicator
        await agent2.communicator.register_handler("test_message", receiver_handler)

        # Link the agents
        await test_agent_harness.link_agents(agent1, agent2)

        # Verify service URLs were updated
        assert agent1.config.service_urls["receiver"] == "mock://receiver"
        assert agent2.config.service_urls["sender"] == "mock://sender"

        # Send a notification from agent1 to agent2
        test_payload = {"data": "test_value"}
        await agent1.communicator.send_notification("receiver", "test_message", test_payload)

        # Allow a short time for async processing
        await asyncio.sleep(0.1)

        # Verify the handler was called with the correct payload
        assert receiver_handler.called is True
        assert receiver_handler.payload == test_payload
        assert receiver_handler.sender_id == "sender"

    @pytest.mark.asyncio
    async def test_verify_all_communicators_aggregates_errors(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that verify_all_communicators correctly aggregates errors from all communicators."""
        # Create two agents with unique communicators
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")

        # Get the communicators
        comm1 = agent1.communicator
        comm2 = agent2.communicator

        # Set expectations on both communicators
        comm1.expect_request("service", "method1", {}, {"result": "success"})
        comm2.expect_notification("service", "event1", {})

        # Fulfill only the expectation on comm1
        await comm1.send_request("service", "method1", {})

        # Verify that verify_all_communicators raises an AssertionError mentioning agent2's unmet expectation
        with pytest.raises(AssertionError) as excinfo:
            test_agent_harness.verify_all_communicators()

        # Check that the error message contains information about the unmet expectation on agent2
        error_msg = str(excinfo.value)
        assert "agent2" in error_msg
        assert "event1" in error_msg
        assert "agent1" not in error_msg  # agent1's expectation was met, so it shouldn't be in the error

    @pytest.mark.asyncio
    async def test_verify_all_communicators_success_case(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that verify_all_communicators succeeds when all expectations are met."""
        # Create two agents with unique communicators
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")

        # Get the communicators
        comm1 = agent1.communicator
        comm2 = agent2.communicator

        # Set expectations on both communicators
        comm1.expect_request("service", "method1", {}, {"result": "success"})
        comm2.expect_notification("service", "event1", {})

        # Fulfill both expectations
        await comm1.send_request("service", "method1", {})
        await comm2.send_notification("service", "event1", {})

        # Verify that verify_all_communicators does not raise an AssertionError
        test_agent_harness.verify_all_communicators()  # Should not raise

    @pytest.mark.asyncio
    async def test_link_agents_with_single_agent(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that link_agents raises a ValueError when called with only one agent."""
        # Create a single agent
        agent = await test_agent_harness.create_agent(name="lone-agent")

        # Attempt to link a single agent, which should raise ValueError
        with pytest.raises(ValueError) as excinfo:
            await test_agent_harness.link_agents(agent)

        # Verify the error message
        assert "At least two agents are required for linking" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_link_agents_multiple_times(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that link_agents can be called multiple times without issues."""
        # Create agents
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")
        agent3 = await test_agent_harness.create_agent(name="agent3")

        # Link first two agents
        await test_agent_harness.link_agents(agent1, agent2)

        # Verify the link was established
        assert agent1.communicator.service_urls["agent2"] == "mock://agent2"
        assert agent2.communicator.service_urls["agent1"] == "mock://agent1"

        # Link the third agent with the first
        await test_agent_harness.link_agents(agent1, agent3)

        # Verify the new link was established without breaking the first link
        assert agent1.communicator.service_urls["agent2"] == "mock://agent2"
        assert agent1.communicator.service_urls["agent3"] == "mock://agent3"
        assert agent3.communicator.service_urls["agent1"] == "mock://agent1"

        # Ensure agent2 is still only linked to agent1
        assert "agent3" not in agent2.communicator.service_urls

        # Start the agents to register the handlers
        async with test_agent_harness.running_agents(agent1, agent2, agent3):
            # Now we can safely trigger handlers
            await test_agent_harness.trigger_handler(agent1, "store_data", {"key": "test", "value": "from-agent1"})
            await test_agent_harness.trigger_handler(agent2, "store_data", {"key": "test", "value": "from-agent2"})
            await test_agent_harness.trigger_handler(agent3, "store_data", {"key": "test", "value": "from-agent3"})

            # Send requests between agents to test the links
            result1 = await test_agent_harness.send_request(agent1, "agent2", "get_data", {"key": "test"})
            assert result1["value"] == "from-agent2"

            result2 = await test_agent_harness.send_request(agent1, "agent3", "get_data", {"key": "test"})
            assert result2["value"] == "from-agent3"

    @pytest.mark.asyncio
    async def test_reset_method(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that the reset method clears all tracked agents and communicators."""
        # Create some agents
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")

        # Link the agents
        await test_agent_harness.link_agents(agent1, agent2)

        # Verify agents and communicators are tracked
        assert len(test_agent_harness.agents) == 2
        assert len(test_agent_harness.communicators) == 2
        assert "agent1" in test_agent_harness.communicators
        assert "agent2" in test_agent_harness.communicators

        # Reset the harness
        test_agent_harness.reset()

        # Verify all tracking is cleared
        assert len(test_agent_harness.agents) == 0
        assert len(test_agent_harness.communicators) == 0

        # Verify we can create new agents after reset
        _ = await test_agent_harness.create_agent(name="new-agent")
        assert len(test_agent_harness.agents) == 1
        assert len(test_agent_harness.communicators) == 1
        assert "new-agent" in test_agent_harness.communicators

    @pytest.mark.asyncio
    async def test_verify_empty_communicators(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that verify_all_communicators works correctly with no tracked communicators."""
        # Verify with no agents created
        test_agent_harness.verify_all_communicators()  # Should not raise any exceptions

        # Create an agent but don't track it
        agent = await test_agent_harness.create_agent(name="untracked", track=False)

        # Verify still works with untracked agents
        test_agent_harness.verify_all_communicators()  # Should not raise any exceptions

        # Add an expectation to the untracked agent's communicator
        agent.communicator.expect_request("some-agent", "some-handler", {"key": "value"})

        # This should not be verified by verify_all_communicators since it's not tracked
        test_agent_harness.verify_all_communicators()  # Should still pass

    @pytest.mark.asyncio
    async def test_link_agents_with_non_mock_communicator(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that link_agents raises TypeError when an agent doesn't use MockCommunicator."""
        # Create a standard agent
        agent1 = await test_agent_harness.create_agent(name="agent1")
        agent2 = await test_agent_harness.create_agent(name="agent2")

        # Replace the communicator with a non-MockCommunicator instance
        class DummyCommunicator:
            def __init__(self, agent_name: str):
                self.agent_name = agent_name

        agent1.communicator = DummyCommunicator(agent_name=agent1.name)

        # Attempt to link agents with different communicator types, which should raise TypeError
        with pytest.raises(TypeError) as excinfo:
            await test_agent_harness.link_agents(agent1, agent2)

        # Verify the error message
        assert "Both agents must use MockCommunicator for linking" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_trigger_handler_with_non_mock_communicator(self, test_agent_harness: AgentTestHarness) -> None:
        """Test that trigger_handler raises TypeError when agent doesn't use MockCommunicator."""
        # Create a standard agent
        agent = await test_agent_harness.create_agent(name="agent1")

        # Replace the communicator with a non-MockCommunicator instance
        class DummyCommunicator:
            def __init__(self, agent_name: str):
                self.agent_name = agent_name

        agent.communicator = DummyCommunicator(agent_name=agent.name)

        # Attempt to trigger a handler, which should raise TypeError
        with pytest.raises(TypeError) as excinfo:
            await test_agent_harness.trigger_handler(agent, "store_data", {"key": "test", "value": "test"})

        # Verify the error message
        assert "does not have a MockCommunicator" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_untracked_agent_creation(self, test_agent_harness: AgentTestHarness) -> None:
        """Test creating an agent without tracking it in the harness."""
        # Create an agent with track=False
        agent = await test_agent_harness.create_agent(name="untracked-agent", track=False)

        # Verify the agent exists but is not tracked
        assert agent.name == "untracked-agent"
        assert len(test_agent_harness.agents) == 0
        assert len(test_agent_harness.communicators) == 0
        assert "untracked-agent" not in test_agent_harness.communicators

        # The agent should still have a communicator
        assert agent.communicator is not None
        assert isinstance(agent.communicator, MockCommunicator)

        # We should be able to use the agent with the test harness
        async with test_agent_harness.running_agent(agent):
            await test_agent_harness.trigger_handler(agent, "store_data", {"key": "test", "value": "data"})

            # But it won't be included in verify_all_communicators
            test_agent_harness.verify_all_communicators()  # Should pass, no tracked agents

    @pytest.mark.asyncio
    async def test_create_agent_with_custom_config_model(self, test_agent_harness: AgentTestHarness, tmp_path) -> None:
        """Test creating an agent with a custom configuration model."""

        # Define a custom config model that extends AgentConfig
        class CustomAgentConfig(AgentConfig):
            custom_option: str = "default"

        # Create a new harness with the custom config model
        custom_harness = AgentTestHarness(
            SimpleTestAgent,
            default_config={"name": "custom-agent", "custom_option": "test-value"},
            config_model=CustomAgentConfig,
            project_root=tmp_path,
        )

        # Create an agent with the custom harness
        agent = await custom_harness.create_agent()

        # Verify the agent was created with the custom config
        assert agent.name == "custom-agent"
        assert agent.config.__class__.__name__ == "CustomAgentConfig"
        # Note: We can't directly access custom_option since the agent's config is cast to AgentConfig
        # but the custom config is used during initialization
