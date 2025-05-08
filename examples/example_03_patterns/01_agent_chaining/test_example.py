"""Test for the agent chaining example using AgentTestHarness with mock communicator."""

import asyncio

import pytest
from agents.consumer.agent import ConsumerAgent
from agents.producer.agent import ProducerAgent

from openmas.testing import expect_sender_request, multi_running_agents, setup_sender_receiver_test
from openmas.testing.mock_communicator import MockCommunicator


@pytest.mark.asyncio
async def test_agent_chaining(tmp_path) -> None:
    """Test that the producer agent successfully chains with the consumer agent."""
    # Set up a producer-consumer test scenario
    producer_harness, consumer_harness, producer, consumer = await setup_sender_receiver_test(
        ProducerAgent, ConsumerAgent, project_root=tmp_path
    )

    # Define the data that the producer will send to the consumer
    test_data = {"data": "test_payload", "timestamp": "2023-01-01T12:00:00Z"}
    expected_response = {"status": "processed", "result": "Modified: test_payload"}

    # Set up expectations for the producer's request to the consumer
    expect_sender_request(
        producer,
        "consumer",
        "process_data",
        test_data,
        expected_response,
    )

    # Start both agents using our multi-agent runner helper
    async with multi_running_agents(producer_harness, producer, consumer_harness, consumer):
        # Trigger producer's run method to send the data
        await producer.run()

        # Allow time for processing if run involves async operations
        await asyncio.sleep(0.1)

        # Verify that the producer recorded the request was sent
        assert producer.data_sent is True

        # Verify that the producer recorded the response
        assert producer.response == expected_response

        # Verify that all expected communications occurred
        if hasattr(producer.communicator, "verify") and isinstance(producer.communicator, MockCommunicator):
            producer.communicator.verify()
