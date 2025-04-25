#!/usr/bin/env python3
"""
Agent Messaging Example.

This example demonstrates how to set up communication between two agents using OpenMAS.
It shows:

1. Creating multiple agents
2. Setting up message handlers
3. Sending and receiving messages between agents
4. Using the built-in communication system

To run:
$ poetry run python examples/communication/agent_messaging.py
"""

import asyncio
import logging
import random
import sys
from typing import Any, Dict, Optional

from openmas.agent import Agent
from openmas.communication import Message
from openmas.config import AgentConfig


class SenderAgent(Agent):
    """An agent that sends messages to another agent."""

    async def setup(self) -> None:
        """Set up the agent and initialize state."""
        await super().setup()
        self.messages_sent = 0
        self.recipient_id: Optional[str] = None
        self.request_types = ["weather", "time", "status", "random_number"]

        # Register handlers for responses
        await self.communicator.register_handler("weather_response", self.handle_weather_response)
        await self.communicator.register_handler("time_response", self.handle_time_response)
        await self.communicator.register_handler("status_response", self.handle_status_response)
        await self.communicator.register_handler("random_number_response", self.handle_random_number_response)

        logging.info(f"SenderAgent {self.name} initialized and ready")

    async def run(self) -> None:
        """Run the agent's main loop."""
        if not self.recipient_id:
            logging.error("No recipient ID configured, can't send messages")
            return

        logging.info(f"SenderAgent {self.name} starting main loop, sending to {self.recipient_id}")

        try:
            while True:
                # Send a request to the receiver
                request_type = random.choice(self.request_types)
                await self.send_request(request_type)

                # Wait before sending the next message
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            logging.info(f"SenderAgent {self.name} run task was cancelled")
            raise

    async def send_request(self, request_type: str) -> None:
        """Send a request to the receiver agent.

        Args:
            request_type: Type of request to send
        """
        if not self.recipient_id:
            return

        message_data: Dict[str, Any] = {"request_type": request_type}

        # Add specific data for certain request types
        if request_type == "random_number":
            message_data["min"] = 1
            message_data["max"] = 100

        # Create and send the message
        message = Message(
            sender_id=self.id, recipient_id=self.recipient_id, content=message_data, message_type=request_type
        )

        await self.communicator.send_message(message)
        self.messages_sent += 1

        logging.info(f"Sent {request_type} request (#{self.messages_sent}) to {self.recipient_id}")

    # Message handler methods

    async def handle_weather_response(self, message: Message) -> None:
        """Handle weather response messages.

        Args:
            message: The received message
        """
        weather_data = message.content
        logging.info(f"Received weather data: {weather_data}")

    async def handle_time_response(self, message: Message) -> None:
        """Handle time response messages.

        Args:
            message: The received message
        """
        time_data = message.content
        logging.info(f"Received time data: {time_data}")

    async def handle_status_response(self, message: Message) -> None:
        """Handle status response messages.

        Args:
            message: The received message
        """
        status_data = message.content
        logging.info(f"Received status data: {status_data}")

    async def handle_random_number_response(self, message: Message) -> None:
        """Handle random number response messages.

        Args:
            message: The received message
        """
        number_data = message.content
        logging.info(f"Received random number: {number_data}")


class ReceiverAgent(Agent):
    """An agent that receives and responds to messages."""

    async def setup(self) -> None:
        """Set up the agent and initialize state."""
        await super().setup()
        self.messages_received = 0
        self.messages_responded = 0

        # Register handlers for requests
        await self.communicator.register_handler("weather", self.handle_weather_request)
        await self.communicator.register_handler("time", self.handle_time_request)
        await self.communicator.register_handler("status", self.handle_status_request)
        await self.communicator.register_handler("random_number", self.handle_random_number_request)

        logging.info(f"ReceiverAgent {self.name} initialized and ready")

    async def run(self) -> None:
        """Run the agent's main loop."""
        logging.info(f"ReceiverAgent {self.name} starting main loop")

        try:
            # This agent just waits for incoming messages
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logging.info(f"ReceiverAgent {self.name} run task was cancelled")
            raise

    async def send_response(self, original_message: Message, response_data: Dict[str, Any], response_type: str) -> None:
        """Send a response to the original sender.

        Args:
            original_message: The message that triggered this response
            response_data: Data to send in the response
            response_type: Type of response being sent
        """
        response = Message(
            sender_id=self.id,
            recipient_id=original_message.sender_id,
            content=response_data,
            message_type=f"{response_type}_response",
            conversation_id=original_message.conversation_id,
        )

        await self.communicator.send_message(response)
        self.messages_responded += 1

        logging.info(f"Sent {response_type} response to {original_message.sender_id}")

    # Request handler methods

    async def handle_weather_request(self, message: Message) -> None:
        """Handle weather request messages.

        Args:
            message: The received message
        """
        self.messages_received += 1
        logging.info(f"Received weather request (#{self.messages_received}) from {message.sender_id}")

        # Simulate weather data
        weather_data = {
            "location": "Example City",
            "temperature": round(random.uniform(0, 35), 1),
            "condition": random.choice(["Sunny", "Cloudy", "Rainy", "Snowy"]),
            "humidity": random.randint(30, 90),
            "timestamp": f"{asyncio.get_event_loop().time():.2f}",
        }

        await self.send_response(message, weather_data, "weather")

    async def handle_time_request(self, message: Message) -> None:
        """Handle time request messages.

        Args:
            message: The received message
        """
        self.messages_received += 1
        logging.info(f"Received time request (#{self.messages_received}) from {message.sender_id}")

        # Simulate time data
        time_data = {"timestamp": f"{asyncio.get_event_loop().time():.2f}", "timezone": "UTC"}

        await self.send_response(message, time_data, "time")

    async def handle_status_request(self, message: Message) -> None:
        """Handle status request messages.

        Args:
            message: The received message
        """
        self.messages_received += 1
        logging.info(f"Received status request (#{self.messages_received}) from {message.sender_id}")

        # Create status data
        status_data = {
            "agent_id": self.id,
            "name": self.name,
            "messages_received": self.messages_received,
            "messages_responded": self.messages_responded,
            "uptime": f"{asyncio.get_event_loop().time() - self._start_time:.2f}",
        }

        await self.send_response(message, status_data, "status")

    async def handle_random_number_request(self, message: Message) -> None:
        """Handle random number request messages.

        Args:
            message: The received message
        """
        self.messages_received += 1
        logging.info(f"Received random number request (#{self.messages_received}) from {message.sender_id}")

        # Extract parameters from the message
        min_val = message.content.get("min", 1)
        max_val = message.content.get("max", 100)

        # Generate a random number
        random_number = random.randint(min_val, max_val)

        number_data = {"number": random_number, "min": min_val, "max": max_val}

        await self.send_response(message, number_data, "random_number")


async def main() -> None:
    """Run the agent messaging example."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stdout
    )

    # Create agent configurations
    sender_config = AgentConfig(name="sender-agent", log_level="INFO", service_urls={})

    receiver_config = AgentConfig(name="receiver-agent", log_level="INFO", service_urls={})

    # Create agent instances
    sender = SenderAgent(config=sender_config)
    receiver = ReceiverAgent(config=receiver_config)

    # Set the recipient ID for the sender
    sender.recipient_id = receiver.id

    try:
        # Start both agents
        logging.info("Starting agents...")
        await asyncio.gather(sender.start(), receiver.start())

        # Let them run for a while
        logging.info("Agents will run for 30 seconds")
        await asyncio.sleep(30)

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received")

    finally:
        # Ensure both agents are properly shut down
        logging.info("Shutting down agents...")
        await asyncio.gather(sender.stop(), receiver.stop())
        logging.info("Example complete")


if __name__ == "__main__":
    asyncio.run(main())
