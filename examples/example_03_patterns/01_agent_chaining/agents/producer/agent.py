"""Producer agent implementation for agent chaining example."""

from openmas.agent import BaseAgent


class ProducerAgent(BaseAgent):
    """An agent that produces data and sends it to a consumer agent."""

    async def setup(self) -> None:
        """Initialize the agent."""
        self.logger.info("Setting up the ProducerAgent")
        self.data_sent = False
        self.response = None

        # Ensure the service URLs are properly set for communication
        if "consumer" not in self.communicator.service_urls:
            self.logger.warning("Consumer service URL not set in configuration, adding default")
            self.communicator.service_urls["consumer"] = "http://localhost:8082"

    async def run(self) -> None:
        """Run the agent, generating and sending data to the consumer."""
        self.logger.info("Producer agent starting...")

        # Log service information for debugging
        self.logger.info(f"Producer service info - URLs: {self.communicator.service_urls}")
        self.logger.info(f"Producer is running with config: {self.config.model_dump()}")

        # Generate some test data
        data = {"data": "test_payload", "timestamp": "2023-01-01T12:00:00Z"}

        self.logger.info(f"Sending data to consumer: {data}")

        # Send the data to the consumer agent
        response = await self.communicator.send_request(target_service="consumer", method="process_data", params=data)

        # Record that we sent the data and received a response
        self.data_sent = True
        self.response = response

        self.logger.info(f"Received response from consumer: {response}")

        # Auto-terminate in all environments (not just CI)
        self.logger.info("Example complete - auto-terminating")

        # Properly signal termination through the agent's lifecycle management
        await self.stop()

    async def shutdown(self) -> None:
        """Clean up resources when the agent is stopped."""
        self.logger.info("Shutting down the ProducerAgent")
