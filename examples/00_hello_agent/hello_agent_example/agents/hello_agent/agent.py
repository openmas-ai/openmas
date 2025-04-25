"""Hello Agent implementation."""

import asyncio
import logging

from openmas.agent import BaseAgent

logger = logging.getLogger(__name__)


class HelloAgent(BaseAgent):
    """A simple agent that says hello."""

    async def setup(self) -> None:
        """Set up the agent."""
        logger.info("Setting up HelloAgent...")

    async def run(self) -> None:
        """Run the agent's main loop."""
        logger.info("Hello from hello_agent!")
        logger.info("COUNTDOWN INITIATED! Prepare for liftoff... or destruction?")

        count = 10
        while count >= 0:
            if count > 0:
                logger.info(f"T-minus {count}...")
            elif count == 0:
                logger.info("🧨 BOOM! 💥 KAPOW! 🔥 KABOOM! 💫")
                logger.info("The agent has self-destructed in the most spectacular way possible!")
                logger.info("Don't worry, no agents were harmed in the making of this example.")

            await asyncio.sleep(1)
            count -= 1

        logger.info("Countdown complete. Agent signing off.")

    async def shutdown(self) -> None:
        """Clean up resources."""
        logger.info("Sweeping up the explosion debris... HelloAgent shutting down...")
