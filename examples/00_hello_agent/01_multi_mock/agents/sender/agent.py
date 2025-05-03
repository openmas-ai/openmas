"""Sender agent for the multi-agent hello world example with mock communicator."""

from openmas.agent import BaseAgent


class SenderAgent(BaseAgent):
    """A simple sender agent that sends a greeting message to the receiver agent."""

    async def setup(self) -> None:
        """Initialize the agent."""
        self.logger.info("Setting up the SenderAgent")
        self.message_sent = False

    async def run(self) -> None:
        """Run the agent, sending a message to the receiver agent."""
        self.logger.info("Sender saying hello (mock)")

        # Send a simple greeting message to the receiver agent
        message = {"greeting": "hello"}
        try:
            await self.communicator.send_request(target_service="receiver", method="handle_message", params=message)
            # Set flag to indicate we sent a message for testing purposes
            self.message_sent = True
            self.logger.info("Message sent to receiver")
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")

    async def shutdown(self) -> None:
        """Clean up when the agent stops."""
        self.logger.info("Shutting down the SenderAgent")
