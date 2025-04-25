"""Example usage of the MQTT communicator with OpenMAS.

This example demonstrates how to use the MQTT communicator in a OpenMAS agent.

To run this example:
1. First start an MQTT broker (e.g., Mosquitto)
   mosquitto -v

2. Run this script
   python mqtt_example.py
"""

import asyncio
import logging
import os
import sys

# Add parent directory to path to import openmas
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import the MQTT communicator
from mqtt_communicator import MqttCommunicator  # noqa: E402

from openmas.agent import BaseAgent  # noqa: E402
from openmas.communication.base import register_communicator  # noqa: E402
from openmas.config import AgentConfig  # noqa: E402

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Register the MQTT communicator
register_communicator("mqtt", MqttCommunicator)


class MqttExampleAgent(BaseAgent):
    """Example agent using MQTT communication."""

    async def setup(self) -> None:
        """Set up the agent."""
        # Register handlers for methods
        await self.communicator.register_handler("get_status", self.handle_get_status)
        await self.communicator.register_handler("echo", self.handle_echo)

        self.logger.info("Agent is ready to receive messages")

    async def run(self) -> None:
        """Run the agent's main loop."""
        try:
            # In a real agent, this would do something useful
            # For this example, we'll just wait forever
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.logger.info("Agent loop cancelled")
            raise

    async def shutdown(self) -> None:
        """Shut down the agent."""
        self.logger.info("Agent shutting down")

    async def handle_get_status(self) -> dict:
        """Handle the get_status method."""
        return {"status": "running", "agent_name": self.name}

    async def handle_echo(self, message: str) -> dict:
        """Handle the echo method."""
        self.logger.info(f"Received echo request: {message}")
        return {"original": message, "echo": message}


async def send_test_messages(agent):
    """Send test messages to demonstrate communication."""
    # Wait for everything to initialize
    await asyncio.sleep(2)

    try:
        # Send a request to ourselves (this agent)
        result = await agent.communicator.send_request(target_service="test_agent", method="get_status", timeout=5.0)
        print(f"Received response from get_status: {result}")

        # Send an echo request
        result = await agent.communicator.send_request(
            target_service="test_agent", method="echo", params={"message": "Hello MQTT!"}, timeout=5.0
        )
        print(f"Received response from echo: {result}")

        # Send a notification
        await agent.communicator.send_notification(
            target_service="test_agent", method="log", params={"message": "This is a notification"}
        )
        print("Sent notification")

    except Exception as e:
        print(f"Error sending test messages: {e}")


async def main():
    """Run the example."""
    # Create and start the agent
    agent = MqttExampleAgent(
        name="mqtt_example_agent",
        config=AgentConfig(
            name="mqtt_example_agent",
            communicator_type="mqtt",
            communicator_options={
                "broker_host": "localhost",
                "broker_port": 1883,
            },
            service_urls={
                # For demonstration, the agent will talk to itself
                "test_agent": "mqtt_example_agent"
            },
        ),
    )

    await agent.start()

    try:
        # Send some test messages
        test_task = asyncio.create_task(send_test_messages(agent))

        # Wait for the test task to complete
        await test_task

        # Keep the agent running for a while
        await asyncio.sleep(5)

    finally:
        # Stop the agent
        await agent.stop()


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
