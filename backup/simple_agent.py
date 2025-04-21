"""A simple example agent using the SimpleMAS SDK."""

import asyncio
from typing import Any, Dict

from simple_mas.agent import BaseAgent
from simple_mas.logging import configure_logging, get_logger

logger = get_logger(__name__)


class SimpleAgent(BaseAgent):
    """A simple agent that periodically pings other services."""

    async def setup(self) -> None:
        """Set up the agent."""
        logger.info("Setting up agent")

        # Register a handler for the "ping" method
        await self.communicator.register_handler("ping", self.handle_ping)

        # Register a handler for the "echo" method
        await self.communicator.register_handler("echo", self.handle_echo)

    async def run(self) -> None:
        """Run the agent's main loop."""
        logger.info("Starting main loop")

        # Get the list of services to ping
        services = list(self.config.service_urls.keys())
        if not services:
            logger.warning("No services configured to ping")
            await asyncio.sleep(float("inf"))  # Sleep forever
            return

        # Ping each service every 5 seconds
        while True:
            for service_name in services:
                try:
                    response = await self.communicator.send_request(
                        service_name, "ping", {"sender": self.name, "message": "Hello!"}
                    )
                    logger.info(f"Received response from {service_name}", response=response)
                except Exception as e:
                    logger.error(f"Error pinging {service_name}", error=str(e))

            # Wait 5 seconds before pinging again
            await asyncio.sleep(5)

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info("Shutting down agent")

    async def handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a ping request.

        Args:
            params: The request parameters

        Returns:
            A response with a greeting
        """
        sender = params.get("sender", "unknown")
        message = params.get("message", "")

        logger.info(f"Received ping from {sender}", message=message)

        return {"greeting": f"Hello, {sender}!", "received_message": message}

    async def handle_echo(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an echo request.

        Args:
            params: The request parameters

        Returns:
            The same parameters
        """
        logger.info("Received echo request", params=params)

        return params


async def main():
    """Run the simple agent."""
    # Configure logging
    configure_logging(log_level="INFO")

    # Create and start the agent
    agent = SimpleAgent(name="simple-agent")

    try:
        await agent.start()

        # Run until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
