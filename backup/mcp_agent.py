"""An example MCP agent using the SimpleMAS SDK."""

import asyncio
from typing import Any, Dict

from simple_mas.agent import BaseAgent
from simple_mas.communication.mcp import McpSseCommunicator
from simple_mas.logging import configure_logging, get_logger

logger = get_logger(__name__)


class McpAgent(BaseAgent):
    """An agent that provides chess-related tools via MCP."""

    async def setup(self) -> None:
        """Set up the agent."""
        logger.info("Setting up MCP agent")

        # Register handlers for MCP methods
        await self.communicator.register_handler("list_resources", self.handle_list_resources)
        await self.communicator.register_handler("get_resource", self.handle_get_resource)
        await self.communicator.register_handler("list_tools", self.handle_list_tools)
        await self.communicator.register_handler("execute_tool", self.handle_execute_tool)

    async def run(self) -> None:
        """Run the agent's main loop."""
        logger.info("MCP agent running - waiting for requests")

        # In a real agent, we might do periodic tasks here
        # For this example, we'll just sleep forever
        await asyncio.sleep(float("inf"))

    async def shutdown(self) -> None:
        """Shut down the agent."""
        logger.info("Shutting down MCP agent")

    # MCP Resource handlers

    async def handle_list_resources(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request to list available resources.

        Args:
            params: The request parameters

        Returns:
            A list of available resources
        """
        logger.info("Listing resources")

        # In a real agent, we would list actual resources
        resources = [
            {
                "uri": "chess://openings/sicilian",
                "name": "Sicilian Defense",
                "description": "Information about the Sicilian Defense opening",
            },
            {
                "uri": "chess://openings/queens-gambit",
                "name": "Queen's Gambit",
                "description": "Information about the Queen's Gambit opening",
            },
        ]

        return {"resources": resources}

    async def handle_get_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request to get a resource.

        Args:
            params: The request parameters with the resource URI

        Returns:
            The resource content
        """
        uri = params.get("uri", "")
        logger.info("Getting resource", uri=uri)

        # In a real agent, we would retrieve the actual resource
        if uri == "chess://openings/sicilian":
            content = (
                "# Sicilian Defense\n\n"
                "The Sicilian Defense is a popular opening that begins with the moves:\n"
                "1. e4 c5\n\n"
                "It is one of the most popular and best-scoring responses to White's first move 1.e4."
            )
            return {"content": content, "mediaType": "text/markdown"}

        elif uri == "chess://openings/queens-gambit":
            content = (
                "# Queen's Gambit\n\n"
                "The Queen's Gambit is a chess opening that begins with the moves:\n"
                "1. d4 d5\n"
                "2. c4\n\n"
                "It is one of the oldest known chess openings."
            )
            return {"content": content, "mediaType": "text/markdown"}

        else:
            # Return an error for unknown resources
            raise ValueError(f"Resource not found: {uri}")

    # MCP Tool handlers

    async def handle_list_tools(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request to list available tools.

        Args:
            params: The request parameters

        Returns:
            A list of available tools
        """
        logger.info("Listing tools")

        # In a real agent, we would list actual tools
        tools = [
            {
                "name": "analyze_position",
                "description": "Analyze a chess position",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fen": {"type": "string", "description": "The position in FEN notation"},
                        "depth": {"type": "integer", "description": "Analysis depth"},
                    },
                    "required": ["fen"],
                },
                "returns": {
                    "type": "object",
                    "properties": {
                        "evaluation": {"type": "number", "description": "Position evaluation in centipawns"},
                        "best_move": {"type": "string", "description": "The best move in UCI notation"},
                    },
                },
            },
            {
                "name": "suggest_move",
                "description": "Suggest a move in the given position",
                "parameters": {
                    "type": "object",
                    "properties": {"fen": {"type": "string", "description": "The position in FEN notation"}},
                    "required": ["fen"],
                },
                "returns": {
                    "type": "object",
                    "properties": {
                        "move": {"type": "string", "description": "The suggested move in UCI notation"},
                        "reason": {"type": "string", "description": "Explanation for the suggested move"},
                    },
                },
            },
        ]

        return {"tools": tools}

    async def handle_execute_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request to execute a tool.

        Args:
            params: The request parameters with the tool name and parameters

        Returns:
            The tool execution result
        """
        tool_name = params.get("name", "")
        tool_params = params.get("parameters", {})
        logger.info("Executing tool", tool=tool_name, params=tool_params)

        # In a real agent, we would execute the actual tool
        if tool_name == "analyze_position":
            # Just get the params but we're not using them in this example
            # since we're returning simulated results
            _ = tool_params.get("fen", "")
            _ = tool_params.get("depth", 10)

            # Simulate analysis
            return {"evaluation": 0.5, "best_move": "e2e4"}  # Slight advantage for white

        elif tool_name == "suggest_move":
            # Just get the params but we're not using them in this example
            _ = tool_params.get("fen", "")

            # Simulate move suggestion
            return {"move": "e7e5", "reason": "Controlling the center is important in the opening"}

        else:
            # Return an error for unknown tools
            raise ValueError(f"Tool not found: {tool_name}")


async def main():
    """Run the MCP agent."""
    # Configure logging
    configure_logging(log_level="INFO")

    # Create and start the agent with the MCP SSE communicator
    agent = McpAgent(name="chess-mcp-agent", communicator_class=McpSseCommunicator)

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
