"""Receiver agent for the multi-agent hello world example with mock communicator."""

from openmas.agent import BaseAgent


class ReceiverAgent(BaseAgent):
    """A simple receiver agent that receives messages from the sender agent."""

    async def setup(self) -> None:
        """Initialize the agent."""
        self.logger.info("Setting up the ReceiverAgent")
        self.message_received = False

        # Register the message handler
        await self.communicator.register_handler("handle_message", self.handle_message)

    async def run(self) -> None:
        """Run the agent - this one just waits for messages."""
        self.logger.info("ReceiverAgent running, waiting for messages")
        # Receiver agent doesn't actively do anything, just waits for messages

    async def handle_message(self, payload: dict) -> dict:
        """Handle incoming messages from other agents.

        Args:
            payload: The message payload

        Returns:
            A response message
        """
        sender_id = "unknown"  # In real communicators this would be provided
        self.logger.info(f"Received message from {sender_id}: {payload}")
        # Set flag to indicate we received a message for testing purposes
        self.message_received = True
        return {"status": "received", "message": "Hello received!"}

    async def shutdown(self) -> None:
        """Clean up when the agent stops."""
        self.logger.info("Shutting down the ReceiverAgent")
