"""Consumer agent implementation for agent chaining example."""

import asyncio
from typing import Any, Dict, List

from openmas.agent import BaseAgent


class ConsumerAgent(BaseAgent):
    """An agent that receives and processes data from a producer agent."""

    async def setup(self) -> None:
        """Initialize the agent and register request handlers."""
        self.logger.info("Setting up the ConsumerAgent")

        # Log service information for debugging
        self.logger.info(f"Consumer service info - URLs: {self.communicator.service_urls}")
        self.logger.info(f"Consumer is running with config: {self.config.model_dump()}")

        # Register the handler for processing data from the producer
        await self.communicator.register_handler("process_data", self.process_data)
        self.logger.info("Registered 'process_data' handler")

        # Track processed requests for testing purposes
        self.processed_requests: List[Dict[str, Any]] = []

    async def process_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Process data received from the producer agent.

        Args:
            params: Parameters received from the producer

        Returns:
            Response indicating the data was processed
        """
        self.logger.info(f"Received data for processing: {params}")

        # Store the request for test verification
        self.processed_requests.append(params)

        # Process the data (in this example, just prepend "Modified: " to the data)
        if "data" in params:
            processed_result = f"Modified: {params['data']}"

            # Create the response
            response = {"status": "processed", "result": processed_result}

            self.logger.info(f"Processing complete. Returning: {response}")
            return response

        # Return error response if no data was provided
        self.logger.warning("Received request without 'data' field")
        return {"status": "error", "message": "No data field found in request"}

    async def run(self) -> None:
        """Run the agent (mostly waiting for incoming requests).

        This agent is primarily passive and waits for incoming requests.
        In a real-world scenario, the agent might run indefinitely, or
        until it receives a signal to stop.
        """
        self.logger.info("Consumer agent running and ready to process requests...")

        # The proper pattern for an indefinitely running agent in OpenMAS
        # is to make the run method wait indefinitely until stopped externally
        self.logger.info("Waiting for producer agent to send data...")

        # Create an event that will never be set
        # This keeps the agent running indefinitely until stopped externally
        stay_alive = asyncio.Event()
        try:
            # Wait indefinitely - this will block until the agent is stopped
            await stay_alive.wait()
        except asyncio.CancelledError:
            # Handle cancellation gracefully
            self.logger.info("Consumer agent run method cancelled")
            raise

    async def shutdown(self) -> None:
        """Clean up resources when the agent is stopped."""
        self.logger.info("Shutting down the ConsumerAgent")
