#!/usr/bin/env python3
"""
Simple Agent Example.

This is a minimal example showing how to create and run a basic agent
using SimpleMAS. This example demonstrates:

1. Creating a custom agent class
2. Configuring and initializing an agent
3. Implementing the core agent lifecycle methods
4. Running an agent with proper setup and shutdown

To run:
$ poetry run python examples/basic/simple_agent.py
"""

import asyncio
import logging
import random
import sys
from typing import Any, Dict, List

from simple_mas.agent import Agent
from simple_mas.config import AgentConfig


class SimpleAgent(Agent):
    """A basic agent that performs random number generation."""

    async def setup(self) -> None:
        """Set up the agent with initial state."""
        await super().setup()  # Always call the parent's setup first

        # Initialize agent state
        self.generated_numbers: List[int] = []
        self.generation_count = 0

        logging.info(f"Agent {self.name} initialized and ready")

    async def run(self) -> None:
        """Run the agent's main loop."""
        logging.info(f"Agent {self.name} starting main loop")

        try:
            # Main agent loop - run until cancelled
            while True:
                # Generate a random number
                number = random.randint(1, 100)
                self.generated_numbers.append(number)
                self.generation_count += 1

                logging.info(f"Generated number: {number} (total: {self.generation_count})")

                # Check if we should report statistics
                if self.generation_count % 5 == 0:
                    self.report_statistics()

                # Wait for next iteration
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logging.info(f"Agent {self.name} run task was cancelled")
            raise

    async def shutdown(self) -> None:
        """Clean up resources before shutting down."""
        logging.info(f"Agent {self.name} shutting down")
        self.report_statistics()
        logging.info(f"Agent {self.name} shutdown complete")

    def report_statistics(self) -> None:
        """Report statistics about the generated numbers."""
        if not self.generated_numbers:
            return

        statistics = {
            "count": len(self.generated_numbers),
            "min": min(self.generated_numbers),
            "max": max(self.generated_numbers),
            "average": sum(self.generated_numbers) / len(self.generated_numbers),
            "last_5": self.generated_numbers[-5:] if len(self.generated_numbers) >= 5 else self.generated_numbers,
        }

        logging.info(f"Statistics: {statistics}")

    async def get_state(self) -> Dict[str, Any]:
        """Get the current state of the agent.

        Returns:
            Dict containing the agent's current state
        """
        return {
            "name": self.name,
            "generated_numbers": self.generated_numbers,
            "generation_count": self.generation_count,
            "last_number": self.generated_numbers[-1] if self.generated_numbers else None,
        }


async def main() -> None:
    """Run the simple agent example."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", stream=sys.stdout
    )

    # Create agent configuration
    config = AgentConfig(
        name="simple-number-generator",
        log_level="INFO",
        service_urls={},  # No external services needed for this example
    )

    # Create agent instance
    agent = SimpleAgent(config=config)

    try:
        # Start the agent (setup + run)
        await agent.start()

        # Keep the agent running for a limited time
        logging.info("Agent will run for 20 seconds")
        await asyncio.sleep(20)

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received")

    finally:
        # Ensure agent is properly shut down
        await agent.stop()
        logging.info("Example complete")


if __name__ == "__main__":
    asyncio.run(main())
