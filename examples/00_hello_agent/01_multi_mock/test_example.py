"""Test for the multi-agent hello world example using AgentTestHarness with mock communicator."""

import asyncio

import pytest
from agents.receiver import ReceiverAgent
from agents.sender import SenderAgent

from openmas.testing import expect_sender_request, multi_running_agents, setup_sender_receiver_test
from openmas.testing.mock_communicator import MockCommunicator


@pytest.mark.asyncio
async def test_hello_pair_mock() -> None:
    """Test that the sender agent successfully sends a message to the receiver agent."""
    # Set up a sender-receiver test scenario
    sender_harness, receiver_harness, sender, receiver = await setup_sender_receiver_test(SenderAgent, ReceiverAgent)

    # Set up expectations for the sender's request to the receiver
    expect_sender_request(
        sender,
        "receiver",
        "handle_message",
        {"greeting": "hello"},
        {"status": "received", "message": "Hello received!"},
    )

    # Start both agents using our multi-agent runner helper
    async with multi_running_agents(sender_harness, sender, receiver_harness, receiver):
        # Trigger sender's run method to send the message
        await sender.run()

        # Allow time for handle_message if run involves async operations
        await asyncio.sleep(0.1)

        # Verify that the sender sent the message
        assert getattr(sender, "message_sent", False) is True

        # Verify that all expected communications occurred
        if hasattr(sender.communicator, "verify") and isinstance(sender.communicator, MockCommunicator):
            sender.communicator.verify()
