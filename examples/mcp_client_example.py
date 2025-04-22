"""Example of SimpleMAS agent using MCP communicators."""

import asyncio
import os

from simple_mas.agent import Agent
from simple_mas.communication.mcp import McpSseCommunicator, McpStdioCommunicator
from simple_mas.config import AgentConfig
from simple_mas.logging import get_logger, setup_logging

# Set up logging
setup_logging()
logger = get_logger(__name__)


class McpExampleAgent(Agent):
    """Example agent using MCP communicators."""

    async def run(self) -> None:
        """Run the agent."""
        logger.info("Starting MCP Example Agent")

        # Get references to the services
        llm_service = "llm"

        try:
            # List available tools
            tools = await self.comm.list_tools(llm_service)
            logger.info(f"Available tools: {tools}")

            # Call a tool
            result = await self.comm.call_tool(
                llm_service, "generate_text", {"prompt": "What is the capital of France?"}
            )
            logger.info(f"Tool result: {result}")

            # List available prompts
            prompts = await self.comm.list_prompts(llm_service)
            logger.info(f"Available prompts: {prompts}")

            # Get a prompt
            prompt_result = await self.comm.get_prompt(
                llm_service, "simple_question", {"question": "What is the capital of France?"}
            )
            logger.info(f"Prompt result: {prompt_result}")

            # List available resources
            resources = await self.comm.list_resources(llm_service)
            logger.info(f"Available resources: {resources}")

            # Read a resource
            resource_result = await self.comm.read_resource(llm_service, "resource://example")
            logger.info(f"Resource result: {resource_result}")

        except Exception as e:
            logger.exception("Error during agent execution", error=str(e))


async def main():
    """Run the example agent."""
    # Determine which transport to use based on environment
    use_sse = os.environ.get("USE_SSE", "false").lower() == "true"

    # Define service URLs
    service_urls = {
        "llm": "http://localhost:8000" if use_sse else "python -m llm_service.main",
    }

    # Create the appropriate MCP communicator based on transport type
    if use_sse:
        communicator = McpSseCommunicator(agent_name="McpExampleAgent", service_urls=service_urls)
    else:
        communicator = McpStdioCommunicator(agent_name="McpExampleAgent", service_urls=service_urls)

    # Create and run the agent
    config = AgentConfig(name="McpExampleAgent")
    agent = McpExampleAgent(config=config, communicator=communicator)

    await agent.start()
    await agent.run()
    await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
