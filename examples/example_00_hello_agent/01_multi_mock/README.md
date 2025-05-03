# Two-Agent Hello World (Mock Communicator Test)

This example demonstrates a simple two-agent interaction using OpenMAS's testing utilities for multi-agent testing.

## Overview

This example consists of two agents:

1. **Sender Agent** - Sends a simple "hello" message to the receiver agent
2. **Receiver Agent** - Receives and logs the message from the sender agent

The agents are configured to use the mock communicator, which allows for testing agent interactions without requiring network connectivity or external services.

## Purpose

This example demonstrates:
- How to use OpenMAS's simplified testing helpers for multi-agent testing
- How to set up mock expectations for agent communication testing
- How to verify that agent communication works correctly using mock communicators
- How to implement and test simple agent message passing

## Running the Test

To run the automated test for this example, execute the following command from the OpenMAS project root:

```bash
tox -e example-00b-hello-pair-mock-test
```

## Test Strategy

Instead of actually sending messages between agents, this example uses:

1. `setup_sender_receiver_test` to create and configure a pair of test agents
2. `expect_sender_request` to set up expectations for what messages should be sent
3. `running_agents` to manage the lifecycle of multiple agents in a single context manager
4. The sender agent's `run()` method to send a request to the receiver
5. `communicator.verify()` to confirm that the send operation was performed as expected

These helper functions simplify multi-agent testing by reducing boilerplate code and providing a more intuitive API.

## Helper Functions

- `setup_sender_receiver_test(sender_class, receiver_class)` - Creates a pair of test agents with their respective harnesses
- `expect_sender_request(sender, target, method, params, response)` - Sets up expectations for a request from sender to receiver
- `running_agents(harness1, agent1, harness2, agent2, ...)` - Runs multiple agents in a single context manager

## Project Structure

- `agents/sender/agent.py` - Implementation of the `SenderAgent` class
- `agents/receiver/agent.py` - Implementation of the `ReceiverAgent` class
- `openmas_project.yml` - Configuration for the two-agent system using mock communicator
- `test_example.py` - Automated test using the helper functions to create, test, and verify the sender's communication
