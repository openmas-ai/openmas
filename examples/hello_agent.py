"""Simple hello agent example."""

import asyncio

from openmas.agent import BaseAgent


class HelloAgent(BaseAgent):
    """A simple agent that prints a greeting message."""

    async def setup(self) -> None:
        """Set up the agent."""
        self.logger.info("Hello agent starting up!")

    async def run(self) -> None:
        """Run the agent."""
        self.logger.info("Hello from the hello agent!")
        # Keep the agent running
        while self._is_running:
            await asyncio.sleep(1)

    async def shutdown(self) -> None:
        """Shut down the agent."""
        self.logger.info("Hello agent shutting down!")


# Example of how to run this agent if executed directly
if __name__ == "__main__":

    async def main() -> None:
        agent = HelloAgent(name="hello")
        await agent.start()
        try:
            # Run for 5 seconds
            await asyncio.sleep(5)
        finally:
            await agent.stop()

    asyncio.run(main())
