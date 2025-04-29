"""Hello World agent implementation for OpenMAS."""

import asyncio

from openmas.agent import BaseAgent


class HelloWorldAgent(BaseAgent):
    """A simple hello world agent that logs a greeting message."""

    async def setup(self) -> None:
        """Initialize the agent."""
        self.logger.info("Setting up the HelloWorldAgent")

    async def run(self) -> None:
        """Run the agent, doing a countdown that ends with KABOOM!."""
        self.logger.info("Hello from Single Agent!")
        self.logger.info("Starting countdown...")

        # Countdown from 5 to 1
        for count in range(5, 0, -1):
            self.logger.info(f"Countdown: {count}...")
            await asyncio.sleep(1)  # Pause for dramatic effect

        # Finish with a KABOOM!
        self.logger.info("🔥 KABOOM! 💥")

        # Sleep a bit more so we can see the KABOOM! before exiting
        await asyncio.sleep(0.5)

    async def shutdown(self) -> None:
        """Clean up resources when the agent is stopped."""
        self.logger.info("Shutting down the HelloWorldAgent")
