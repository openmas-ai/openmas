#!/usr/bin/env python3
"""
Hello World Example for SimpleMAS.

This is a minimal example demonstrating the basic structure of agents
in the SimpleMAS framework. It shows:
1. How to create and configure agents
2. How to implement message handling
3. How to run agents in an asynchronous environment

To run:
$ poetry run python examples/basic/hello_world.py
"""

import asyncio
import logging
import sys
from typing import Any, Dict, Optional, Type

from simple_mas.agent.base import BaseAgent
from simple_mas.communication import BaseCommunicator, HttpCommunicator, get_communicator_class
from simple_mas.config import AgentConfig


# Define a Message class to use for communication
class Message:
    """A message for communication between agents."""

    def __init__(
        self,
        sender_id: str,
        recipient_id: str,
        content: Dict[str, Any],
        message_type: str,
        conversation_id: Optional[str] = None,
    ):
        """Initialize a message.

        Args:
            sender_id: ID of the sender
            recipient_id: ID of the recipient
            content: Message content
            message_type: Type of message
            conversation_id: Optional conversation ID
        """
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.content = content
        self.message_type = message_type
        self.conversation_id = conversation_id


class HelloAgent(BaseAgent):
    """A simple agent that says hello when receiving a message."""

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[AgentConfig] = None,
        communicator_class: Optional[Type[BaseCommunicator]] = None,
    ):
        """Initialize the agent.

        Args:
            name: The name of the agent
            config: The agent configuration
            communicator_class: The communicator class to use
        """
        # If config is provided and communicator_class is not, get it from the config
        if config is not None and communicator_class is None and getattr(config, "communicator_type", None):
            # Use the communicator type from config
            communicator_class = get_communicator_class(config.communicator_type)

        # Call the parent constructor with the configuration object directly
        super().__init__(name=name, config=config, communicator_class=communicator_class or HttpCommunicator)
        self.greetings_received = 0

    @property
    def id(self) -> str:
        """Get the agent ID (same as name for this example).

        Returns:
            Agent ID
        """
        return self.name

    async def setup(self) -> None:
        """Set up the agent."""
        # Implement the abstract method with real functionality
        # Don't call super().setup() since it's abstract with no implementation

        # Register a message handler for "greeting" type messages
        await self.communicator.register_handler("greeting", self.handle_greeting)

        # Initialize state
        self.greetings_received = 0
        logging.info(f"Agent {self.name} initialized and ready")

    async def run(self) -> None:
        """Run the agent's main loop."""
        logging.info(f"Agent {self.name} running")
        try:
            # Just wait until cancelled
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logging.info(f"Agent {self.name} was cancelled")
            raise

    async def shutdown(self) -> None:
        """Clean up resources before shutdown."""
        logging.info(f"Agent {self.name} shutting down")
        # No special cleanup needed for this example

    async def handle_greeting(self, message: Any) -> None:
        """Handle a greeting message by responding with another greeting.

        Args:
            message: The greeting message (can be an object or dictionary)
        """
        # Support both dictionary and object-style messages
        if isinstance(message, dict):
            sender = message.get("sender_id") or message["content"].get("sender_id")
            greeting = message["content"].get("text", "Hello")
        else:
            sender = message.sender_id
            greeting = message.content.get("text", "Hello")

        # Increment counter
        self.greetings_received += 1

        logging.info(f"Received greeting from {sender}: {greeting}")

        # Create response content
        response_content = {
            "text": f"Hello back, {sender}! This is {self.name}.",
            "greeting_number": self.greetings_received,
        }

        # Use the send_notification method for mocked and real communicators
        await self.communicator.send_notification(sender, "greeting_response", response_content)
        logging.info(f"Sent greeting response to {sender}")


class SenderAgent(BaseAgent):
    """An agent that sends greeting messages to other agents."""

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[AgentConfig] = None,
        communicator_class: Optional[Type[BaseCommunicator]] = None,
    ):
        """Initialize the agent.

        Args:
            name: The name of the agent
            config: The agent configuration
            communicator_class: The communicator class to use
        """
        # If config is provided and communicator_class is not, get it from the config
        if config is not None and communicator_class is None and getattr(config, "communicator_type", None):
            # Use the communicator type from config
            communicator_class = get_communicator_class(config.communicator_type)

        # Call the parent constructor with the configuration object directly
        super().__init__(name=name, config=config, communicator_class=communicator_class or HttpCommunicator)
        self.target_agent_id = ""
        self.messages_sent = 0
        self.responses_received = 0

    @property
    def id(self) -> str:
        """Get the agent ID (same as name for this example).

        Returns:
            Agent ID
        """
        return self.name

    async def setup(self) -> None:
        """Set up the agent."""
        # Implement the abstract method with real functionality
        # Don't call super().setup() since it's abstract with no implementation

        # Register handler for greeting responses
        await self.communicator.register_handler("greeting_response", self.handle_response)

        # Initialize state
        self.messages_sent = 0
        self.responses_received = 0

        logging.info(f"Agent {self.name} initialized and ready")

    async def run(self) -> None:
        """Run the agent's main logic."""
        logging.info(f"Agent {self.name} starting to send greetings")

        try:
            # Send 5 greetings with 1-second intervals
            greetings = [
                "Hello there!",
                "How are you today?",
                "Nice to meet you!",
                "Greetings from SimpleMAS!",
                "Hello one last time!",
            ]

            for greeting in greetings:
                if self.target_agent_id:
                    await self._send_greeting(greeting)
                    self.messages_sent += 1
                    await asyncio.sleep(1)
                else:
                    logging.warning("No target agent specified, can't send greetings")
                    break

            # Wait a bit for final responses
            await asyncio.sleep(1)

            logging.info(f"Sent {self.messages_sent} greetings, received {self.responses_received} responses")

        except asyncio.CancelledError:
            logging.info(f"Agent {self.name} run task was cancelled")
            raise

    async def shutdown(self) -> None:
        """Clean up resources before shutdown."""
        logging.info(f"Agent {self.name} shutting down")
        # No special cleanup needed

    async def _send_greeting(self, text: str) -> None:
        """Send a greeting message to the target agent.

        Args:
            text: The greeting text to send
        """
        if not self.target_agent_id:
            logging.warning("No target agent specified, setting to default 'test_recipient'")
            self.target_agent_id = "test_recipient"

        # Create message content
        content = {"text": text, "message_number": self.messages_sent + 1}

        # Use the send_notification method for mocked and real communicators
        await self.communicator.send_notification(self.target_agent_id, "greeting", content)
        logging.info(f"Sent greeting to {self.target_agent_id}: {text}")

    async def handle_response(self, message: Any) -> None:
        """Handle response messages from other agents.

        Args:
            message: The response message (can be an object or dictionary)
        """
        # Support both dictionary and object-style messages
        if isinstance(message, dict):
            sender = message.get("sender_id") or message["content"].get("sender_id")
            response_text = message["content"].get("text", "")
        else:
            sender = message.sender_id
            response_text = message.content.get("text", "")

        self.responses_received += 1

        logging.info(f"Received response from {sender}: {response_text}")


async def main() -> None:
    """Run the hello world example with two agents exchanging greetings."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stdout
    )

    # Create agent configurations
    hello_agent_config = AgentConfig(
        name="hello_agent", log_level="INFO", communicator_type="in-memory", service_urls={}
    )

    sender_agent_config = AgentConfig(
        name="sender_agent", log_level="INFO", communicator_type="in-memory", service_urls={}
    )

    # Create agent instances
    # When running directly, create agents with direct config
    hello_agent = HelloAgent(name=hello_agent_config.name, config=hello_agent_config)

    sender_agent = SenderAgent(name=sender_agent_config.name, config=sender_agent_config)

    # Set the target agent ID for the sender
    sender_agent.target_agent_id = hello_agent.name

    try:
        # Start both agents
        logging.info("Starting agents...")
        await asyncio.gather(hello_agent.start(), sender_agent.start())

        # Let the agents run until the sender completes all messages
        await asyncio.sleep(10)

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received")

    finally:
        # Ensure both agents are properly shut down
        logging.info("Shutting down agents...")
        await asyncio.gather(hello_agent.stop(), sender_agent.stop())
        logging.info("Example complete")


if __name__ == "__main__":
    asyncio.run(main())
