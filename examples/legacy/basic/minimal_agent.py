#!/usr/bin/env python3
"""
Minimal Agent Example.

This example demonstrates the most basic setup of a OpenMAS agent.
It shows:

1. Creating a simple agent
2. Handling setup, run, and cleanup methods
3. Basic message sending and receiving
4. Proper agent lifecycle management

To run:
$ poetry run python examples/basic/minimal_agent.py
"""

import asyncio
import logging
import sys
from typing import Optional

from openmas.agent import Agent
from openmas.communication import Message
from openmas.config import AgentConfig


class MinimalAgent(Agent):
    """A minimal agent implementation."""

    async def setup(self) -> None:
        """Set up the agent and initialize state."""
        # First, call the parent setup method
        await super().setup()

        # Initialize agent state
        self.counter = 0
        self.received_messages = 0

        # Register message handlers
        await self.communicator.register_handler("ping", self.handle_ping)
        await self.communicator.register_handler("status_request", self.handle_status_request)

        logging.info(f"Agent {self.name} initialized and ready")

    async def run(self) -> None:
        """Run the agent's main loop."""
        logging.info(f"Agent {self.name} starting main loop")

        try:
            # Run for a set number of iterations
            max_iterations = 10

            while self.counter < max_iterations:
                # Increment counter
                self.counter += 1
                logging.info(f"Agent {self.name} iteration {self.counter}")

                # Simulate some work
                await asyncio.sleep(1)

            logging.info(f"Agent {self.name} completed {max_iterations} iterations")

        except asyncio.CancelledError:
            logging.info(f"Agent {self.name} run task was cancelled")
            raise

    async def cleanup(self) -> None:
        """Clean up resources before agent shutdown."""
        logging.info(f"Agent {self.name} cleaning up resources")

        # Release any resources here

        # Call parent cleanup
        await super().cleanup()

    async def handle_ping(self, message: Message) -> None:
        """Handle a ping message.

        Args:
            message: The received message
        """
        self.received_messages += 1
        logging.info(f"Received ping from {message.sender_id}: {message.content}")

        # Prepare a pong response
        pong_content = {"message": "pong", "counter": self.counter, "original_ping": message.content.get("message", "")}

        # Create and send the response
        response = Message(
            sender_id=self.id,
            recipient_id=message.sender_id,
            content=pong_content,
            message_type="pong",
            conversation_id=message.conversation_id,
        )

        await self.communicator.send_message(response)
        logging.info(f"Sent pong to {message.sender_id}")

    async def handle_status_request(self, message: Message) -> None:
        """Handle a status request message.

        Args:
            message: The received message
        """
        self.received_messages += 1
        logging.info(f"Received status request from {message.sender_id}")

        # Prepare status data
        status_data = {
            "agent_name": self.name,
            "agent_id": self.id,
            "iteration": self.counter,
            "messages_received": self.received_messages,
            "status": "running" if self.counter < 10 else "completed",
        }

        # Create and send the response
        response = Message(
            sender_id=self.id,
            recipient_id=message.sender_id,
            content=status_data,
            message_type="status_response",
            conversation_id=message.conversation_id,
        )

        await self.communicator.send_message(response)
        logging.info(f"Sent status to {message.sender_id}")


class PingAgent(Agent):
    """A simple agent that sends ping messages to another agent."""

    async def setup(self) -> None:
        """Set up the agent and initialize state."""
        await super().setup()
        self.target_agent_id: Optional[str] = None
        self.pings_sent = 0
        self.pongs_received = 0
        self.status_requests_sent = 0

        # Register handlers
        await self.communicator.register_handler("pong", self.handle_pong)
        await self.communicator.register_handler("status_response", self.handle_status_response)

        logging.info(f"PingAgent {self.name} initialized and ready")

    async def run(self) -> None:
        """Run the agent's main loop."""
        if not self.target_agent_id:
            logging.error("No target agent ID configured")
            return

        logging.info(f"PingAgent {self.name} starting main loop")

        try:
            # Send pings every 2 seconds
            while self.pings_sent < 5:
                # Send a ping
                await self._send_ping()
                self.pings_sent += 1

                # Every other ping, also send a status request
                if self.pings_sent % 2 == 0:
                    await self._send_status_request()
                    self.status_requests_sent += 1

                # Wait before next ping
                await asyncio.sleep(2)

            # Send one final status request
            await self._send_status_request()
            self.status_requests_sent += 1

            logging.info(f"PingAgent {self.name} completed sending {self.pings_sent} pings")
            logging.info(f"Received {self.pongs_received} pongs in response")

        except asyncio.CancelledError:
            logging.info(f"PingAgent {self.name} run task was cancelled")
            raise

    async def _send_ping(self) -> None:
        """Send a ping message to the target agent."""
        ping_content = {
            "message": "ping",
            "sequence": self.pings_sent + 1,
            "timestamp": str(asyncio.get_event_loop().time()),
        }

        # Create and send the message
        message = Message(
            sender_id=self.id, recipient_id=self.target_agent_id, content=ping_content, message_type="ping"
        )

        await self.communicator.send_message(message)
        logging.info(f"Sent ping #{self.pings_sent + 1} to {self.target_agent_id}")

    async def _send_status_request(self) -> None:
        """Send a status request to the target agent."""
        request_content = {"request": "status", "sequence": self.status_requests_sent + 1}

        # Create and send the message
        message = Message(
            sender_id=self.id, recipient_id=self.target_agent_id, content=request_content, message_type="status_request"
        )

        await self.communicator.send_message(message)
        logging.info(f"Sent status request #{self.status_requests_sent + 1} to {self.target_agent_id}")

    async def handle_pong(self, message: Message) -> None:
        """Handle a pong response.

        Args:
            message: The received message
        """
        self.pongs_received += 1
        pong_data = message.content

        logging.info(f"Received pong from {message.sender_id}")
        logging.info(f"Pong details: counter={pong_data.get('counter')}, message={pong_data.get('message')}")

    async def handle_status_response(self, message: Message) -> None:
        """Handle a status response.

        Args:
            message: The received message
        """
        status_data = message.content

        logging.info(f"Received status from {message.sender_id}")
        logging.info(f"Agent {status_data.get('agent_name')} (ID: {status_data.get('agent_id')})")
        logging.info(f"Status: {status_data.get('status')}")
        logging.info(f"Iteration: {status_data.get('iteration')}")
        logging.info(f"Messages received: {status_data.get('messages_received')}")


async def main() -> None:
    """Run the minimal agent example."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stdout
    )

    # Create agent configurations
    minimal_config = AgentConfig(name="minimal-agent", log_level="INFO", service_urls={})

    ping_config = AgentConfig(name="ping-agent", log_level="INFO", service_urls={})

    # Create agent instances
    minimal_agent = MinimalAgent(config=minimal_config)
    ping_agent = PingAgent(config=ping_config)

    # Set the minimal agent as the target for the ping agent
    ping_agent.target_agent_id = minimal_agent.id

    try:
        # Start both agents
        logging.info("Starting agents...")
        await asyncio.gather(minimal_agent.start(), ping_agent.start())

        # Let the agents run for a while
        # They will complete their tasks based on their internal logic
        await asyncio.sleep(20)

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received")

    finally:
        # Ensure both agents are properly shut down
        logging.info("Shutting down agents...")
        await asyncio.gather(minimal_agent.stop(), ping_agent.stop())
        logging.info("Example complete")


if __name__ == "__main__":
    asyncio.run(main())
