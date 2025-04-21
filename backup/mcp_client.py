"""An example MCP client using the SimpleMAS SDK."""

import asyncio
import os

from simple_mas.agent import BaseAgent
from simple_mas.communication.mcp import McpSseCommunicator
from simple_mas.config import AgentConfig
from simple_mas.logging import configure_logging, get_logger

logger = get_logger(__name__)


class McpClientAgent(BaseAgent):
    """An agent that connects to an MCP server and uses its resources and tools."""

    async def setup(self) -> None:
        """Set up the agent."""
        logger.info("Setting up MCP client agent")

        # The server name should be in the service_urls config
        self.server_name = next(iter(self.config.service_urls.keys()), None)
        if not self.server_name:
            logger.error("No MCP server configured in service_urls")
            return

        logger.info("Will connect to MCP server: {}".format(self.server_name))

    async def run(self) -> None:
        """Run the agent's main loop."""
        logger.info("Starting MCP client agent")

        if not self.server_name:
            logger.error("No MCP server configured, exiting")
            return

        try:
            # Initialize the MCP connection
            # This happens automatically when we make the first request

            # List available resources
            logger.info("Listing resources")
            resources_response = await self.communicator.send_request(self.server_name, "list_resources", {})
            resources = resources_response.get("resources", [])
            logger.info("Found {} resources".format(len(resources)))

            # Get a specific resource
            if resources:
                resource_uri = resources[0]["uri"]
                logger.info("Getting resource: {}".format(resource_uri))
                resource_response = await self.communicator.send_request(
                    self.server_name, "get_resource", {"uri": resource_uri}
                )
                logger.info("Retrieved resource content:")
                logger.info(resource_response.get("content", ""))

            # List available tools
            logger.info("Listing tools")
            tools_response = await self.communicator.send_request(self.server_name, "list_tools", {})
            tools = tools_response.get("tools", [])
            logger.info("Found {} tools".format(len(tools)))

            # Execute a tool
            if tools:
                tool_name = tools[0]["name"]
                logger.info("Executing tool: {}".format(tool_name))
                tool_params = {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}
                tool_response = await self.communicator.send_request(
                    self.server_name, "execute_tool", {"name": tool_name, "parameters": tool_params}
                )
                logger.info("Tool execution result: {}".format(tool_response))

            logger.info("MCP client demonstration completed")

        except Exception as e:
            logger.exception("Error in MCP client", error=str(e))

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info("Shutting down MCP client agent")


async def main():
    """Run the MCP client agent."""
    # Configure logging
    configure_logging(log_level="INFO")

    # Set up service URLs
    service_urls = {"chess-server": os.environ.get("MCP_SERVER_URL", "http://localhost:8000")}

    # Create and start the agent
    agent = McpClientAgent(
        name="chess-client",
        communicator_class=McpSseCommunicator,
        config=AgentConfig(name="chess-client", service_urls=service_urls),
    )

    try:
        await agent.start()
        # The agent will run its tasks and then exit
        await asyncio.sleep(2)  # Give it a moment to complete
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
