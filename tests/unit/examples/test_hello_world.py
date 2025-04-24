#!/usr/bin/env python3
"""
Unit tests for the hello_world.py example.

This demonstrates how to test agent behavior using the SimpleMAS testing utilities.
"""

import asyncio

import pytest

# Import the agent classes from the example
from examples.basic.hello_world import HelloAgent, Message, SenderAgent
from simple_mas.config import AgentConfig
from simple_mas.testing.mock_communicator import MockCommunicator

# These imports are no longer needed as the registration is handled globally
# from simple_mas.communication.base import register_communicator
# from simple_mas.communication.http import HttpCommunicator

# Registration is now handled by the global conftest.py fixture
# register_communicator("mock", MockCommunicator)
# register_communicator("http", HttpCommunicator)


class TestHelloWorldExample:
    """Test suite for the HelloAgent and SenderAgent classes."""

    @pytest.fixture
    def hello_agent_config(self) -> AgentConfig:
        """Create a test configuration for the HelloAgent.

        Returns:
            AgentConfig with test settings
        """
        return AgentConfig(name="test_hello_agent", log_level="DEBUG", communicator_type="mock", service_urls={})

    @pytest.fixture
    def sender_agent_config(self) -> AgentConfig:
        """Create a test configuration for the SenderAgent.

        Returns:
            AgentConfig with test settings
        """
        return AgentConfig(name="test_sender_agent", log_level="DEBUG", communicator_type="mock", service_urls={})

    @pytest.mark.asyncio
    async def test_hello_agent_responds_to_greeting(self, hello_agent_config: AgentConfig) -> None:
        """Test that HelloAgent responds correctly to a greeting message.

        Args:
            hello_agent_config: Test agent configuration
        """
        # Create and set up the agent
        agent = HelloAgent(config=hello_agent_config)
        await agent.start()

        try:
            # Get the mock communicator
            communicator = agent.communicator
            assert isinstance(communicator, MockCommunicator)

            # Create a test greeting message
            greeting_message = Message(
                sender_id="test_sender",
                recipient_id=agent.id,
                content={"text": "Hello there!"},
                message_type="greeting",
            )

            # Send the message to the agent
            await communicator.simulate_receive_message(greeting_message)

            # Check that a response was sent
            sent_messages = communicator.get_sent_messages()
            assert len(sent_messages) == 1

            # Verify the response content
            response = sent_messages[0]
            assert response["recipient_id"] == "test_sender"
            assert "Hello back" in response["content"].get("text", "")
            assert response["message_type"] == "greeting_response"
            assert response["content"].get("greeting_number") == 1

        finally:
            await agent.stop()

    @pytest.mark.asyncio
    async def test_hello_agent_counts_greetings(self, hello_agent_config: AgentConfig) -> None:
        """Test that HelloAgent correctly counts the number of greetings received.

        Args:
            hello_agent_config: Test agent configuration
        """
        # Create and set up the agent
        agent = HelloAgent(config=hello_agent_config)
        await agent.start()

        try:
            # Get the mock communicator
            communicator = agent.communicator
            assert isinstance(communicator, MockCommunicator)

            # Send multiple greeting messages
            for i in range(3):
                greeting_message = Message(
                    sender_id="test_sender",
                    recipient_id=agent.id,
                    content={"text": f"Greeting {i+1}"},
                    message_type="greeting",
                )
                await communicator.simulate_receive_message(greeting_message)

            # Check that the correct number of responses were sent
            sent_messages = communicator.get_sent_messages()
            assert len(sent_messages) == 3

            # Verify the greeting counter in the last response
            last_response = sent_messages[-1]
            assert last_response["content"].get("greeting_number") == 3

            # Verify the agent's internal state
            assert agent.greetings_received == 3

        finally:
            await agent.stop()

    @pytest.mark.asyncio
    async def test_sender_agent_sends_greetings(self, sender_agent_config: AgentConfig) -> None:
        """Test that SenderAgent correctly sends greeting messages.

        Args:
            sender_agent_config: Test agent configuration
        """
        # Create and set up the agent
        agent = SenderAgent(config=sender_agent_config)

        # Set the target agent ID
        agent.target_agent_id = "test_recipient"

        await agent.start()

        try:
            # Get the mock communicator
            communicator = agent.communicator
            assert isinstance(communicator, MockCommunicator)

            # Explicitly send a greeting
            await agent._send_greeting("Test greeting")

            # Check that messages were sent
            sent_messages = communicator.get_sent_messages()

            # Verify that at least one message was sent
            assert len(sent_messages) >= 1

            # Verify the message structure
            first_message = sent_messages[0]
            assert first_message["sender_id"] == agent.id
            assert first_message["recipient_id"] == "test_recipient"
            assert first_message["message_type"] == "greeting"
            assert "text" in first_message["content"]
            assert "message_number" in first_message["content"]

        finally:
            await agent.stop()

    @pytest.mark.asyncio
    async def test_sender_agent_handles_responses(self, sender_agent_config: AgentConfig) -> None:
        """Test that SenderAgent correctly handles response messages.

        Args:
            sender_agent_config: Test agent configuration
        """
        # Create and set up the agent
        agent = SenderAgent(config=sender_agent_config)
        await agent.start()

        try:
            # Get the mock communicator
            communicator = agent.communicator
            assert isinstance(communicator, MockCommunicator)

            # Create and send response messages
            for i in range(2):
                response_message = Message(
                    sender_id="test_responder",
                    recipient_id=agent.id,
                    content={"text": f"Response {i+1}"},
                    message_type="greeting_response",
                )
                await communicator.simulate_receive_message(response_message)

            # Verify that the responses were counted
            assert agent.responses_received == 2

        finally:
            await agent.stop()

    @pytest.mark.asyncio
    async def test_integration_between_agents(
        self, hello_agent_config: AgentConfig, sender_agent_config: AgentConfig
    ) -> None:
        """Test the interaction between HelloAgent and SenderAgent.

        This test simulates the integration between the two agent types,
        verifying that they can communicate with each other correctly.

        Args:
            hello_agent_config: Test configuration for HelloAgent
            sender_agent_config: Test configuration for SenderAgent
        """
        # Create the agents
        hello_agent = HelloAgent(config=hello_agent_config)
        sender_agent = SenderAgent(config=sender_agent_config)

        # Configure the sender to target the hello agent
        sender_agent.target_agent_id = hello_agent.id

        # Get the communicators
        hello_comm = hello_agent.communicator
        sender_comm = sender_agent.communicator
        assert isinstance(hello_comm, MockCommunicator)
        assert isinstance(sender_comm, MockCommunicator)

        # Link the communicators so they can talk to each other
        hello_comm.link_communicator(sender_comm)

        # Start both agents
        await hello_agent.start()
        await sender_agent.start()

        try:
            # Send a greeting directly through the communicator to ensure it works
            await sender_comm.send_notification(
                hello_agent.id, "greeting", {"text": "Test greeting", "sender_id": sender_agent.id}
            )

            # Wait for message processing - give it a bit more time
            await asyncio.sleep(0.3)

            # Verify the hello agent received the greeting
            assert hello_agent.greetings_received > 0

            # Check the sender agent's sent messages
            sender_messages = sender_comm.get_sent_messages()
            assert len(sender_messages) >= 1

            # Check the hello agent's sent messages
            hello_messages = hello_comm.get_sent_messages()
            assert len(hello_messages) >= 1
            assert hello_messages[0]["message_type"] == "greeting_response"
            assert hello_messages[0]["recipient_id"] == sender_agent.id

        finally:
            await hello_agent.stop()
            await sender_agent.stop()
