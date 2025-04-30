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

        # Auto-terminate in all environments (not just CI)
        self.logger.info("Example complete - auto-terminating")
        # Signal the agent to stop
        await self.stop()

        # """
        # # ==========================================
        # # ALTERNATIVE: INDEFINITE RUNNING PATTERN
        # # ==========================================
        # # This is the typical pattern for production agents that should run until
        # # externally terminated (e.g., with Ctrl+C).
        # # In this case, the CLI will block until the user presses Ctrl+C.

        # # Example of a run method that continues indefinitely:

        # self.logger.info("Starting indefinite agent operation...")

        # try:
        # Create an asyncio Future that will never complete on its own
        # This is cleaner than using while True with sleep
        #    never_complete = asyncio.Future()

        # You can set up periodic tasks using background tasks
        #    self._check_interval = 10  # seconds
        #    self.create_background_task(self._periodic_check())

        # Wait forever (or until cancelled by Ctrl+C)
        #    await never_complete

        # except asyncio.CancelledError:
        # This will be triggered when the agent is stopped
        #    self.logger.info("Agent execution cancelled")
        #    raise  # Important: re-raise the exception to allow proper cleanup

    # async def _periodic_check(self) -> None:
    # Example background task that runs periodically
    # while True:
    # try:
    # self.logger.info("Performing periodic check...")
    # Do regular maintenance work here

    # Wait until next check interval
    # await asyncio.sleep(self._check_interval)

    # except asyncio.CancelledError:
    # self.logger.info("Periodic check task cancelled")
    # break  # Exit the loop when cancelled
    # """

    async def shutdown(self) -> None:
        """Clean up resources when the agent is stopped."""
        self.logger.info("Shutting down the HelloWorldAgent")
