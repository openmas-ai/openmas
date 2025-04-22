"""MCP Server Agent implementation for SimpleMAS.

This module provides a server-side Model Context Protocol (MCP) agent implementation that can be used
to expose functionality to MCP clients (like Claude) using FastMCP.
"""

from typing import Any, Dict, Optional

from simple_mas.agent.mcp import McpAgent


class McpServerAgent(McpAgent):
    """Server agent that exposes MCP tools, prompts, and resources.

    This specialized agent is designed to run as an MCP server, exposing functionality
    through tools, prompts, and resources that can be accessed by MCP clients.

    It leverages the base McpAgent functionality for discovering decorated methods
    and works with McpSseCommunicator or McpStdioCommunicator in server mode to handle
    the actual server setup and communication.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        server_type: str = "sse",
        host: str = "0.0.0.0",
        port: int = 8000,
        **kwargs: Any,
    ):
        """Initialize the MCP server agent.

        Args:
            name: Optional name for the agent
            config: Optional configuration for the agent
            server_type: The type of server to create ('sse' or 'stdio')
            host: The host to bind to (for 'sse' server type)
            port: The port to bind to (for 'sse' server type)
            **kwargs: Additional keyword arguments for the parent class
        """
        super().__init__(name=name, config=config, **kwargs)

        self.server_type = server_type
        self.host = host
        self.port = port

        # Set server mode flag to help the communicator know it should act as a server
        self._server_mode = True

    def setup_communicator(self, instructions: Optional[str] = None) -> None:
        """Set up the appropriate communicator based on server_type.

        Args:
            instructions: Optional instructions for the MCP server
        """
        from simple_mas.communication.mcp import McpSseCommunicator, McpStdioCommunicator

        if self.server_type.lower() == "sse":
            from fastapi import FastAPI

            # Create FastAPI app
            app = FastAPI(title=f"{self.name} MCP Server")

            # Create SSE communicator in server mode
            communicator = McpSseCommunicator(
                agent_name=self.name,
                service_urls={},  # Empty as we're a server
                server_mode=True,
                http_port=self.port,
                server_instructions=instructions,
                app=app,
            )

        elif self.server_type.lower() == "stdio":
            # Create stdio communicator in server mode
            communicator = McpStdioCommunicator(
                agent_name=self.name,
                service_urls={},  # Empty as we're a server
                server_mode=True,
                server_instructions=instructions,
            )

        else:
            raise ValueError(f"Unsupported server type: {self.server_type}")

        # Set the communicator for this agent
        self.set_communicator(communicator)

    async def start_server(self, instructions: Optional[str] = None) -> None:
        """Start the MCP server.

        This is a convenience method that sets up the communicator if needed
        and starts it.

        Args:
            instructions: Optional instructions for the MCP server
        """
        # Set up communicator if not done already
        if not self.communicator:
            self.setup_communicator(instructions)

        # Start the communicator (which starts the server)
        await self.communicator.start()

    async def stop_server(self) -> None:
        """Stop the MCP server.

        This is a convenience method that stops the communicator,
        which in turn stops the server.
        """
        if self.communicator:
            await self.communicator.stop()
